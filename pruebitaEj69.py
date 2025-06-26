import os
import sys
import time
import threading
import sqlite3
import webbrowser as web
from datetime import datetime, timedelta

import pandas as pd
import pyautogui as pg
import schedule

import tkinter as tk
from tkinter import filedialog, ttk, Scrollbar

import customtkinter as ctk

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from flask import Flask, request, jsonify, send_file, render_template, send_from_directory

from fpdf import FPDF

import pyttsx3


# Detectar si estás corriendo desde un .exe
#if getattr(sys, 'frozen', False):
    # Ruta del ejecutable compilado
    #base_path = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
#else:
    # Ruta del script original
    #base_path = os.path.dirname(os.path.abspath(__file__))

# Ruta absoluta a la base de datos
#db_path = os.path.join(base_path, "programa_mensajes.db")

# Ruta absoluta al Excel (si es fijo)
#excel_path_global = os.path.join(base_path, "CLIENTES LUBRISERVICIO BARANOA - ACTUALIZADA - MACRO2.xlsm")



# Configuración inicial de customtkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Ruta global del archivo Excel
excel_path_global = "CLIENTES LUBRISERVICIO BARANOA - ACTUALIZADA - MACRO2.xlsm"


# Crear o actualizar la base de datos

def inicializar_db():
    conexion = sqlite3.connect("programa_mensajes.db")
    cursor = conexion.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mensajes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            placa TEXT,
            fecha_ultimo_cambio TEXT,
            nombre TEXT,
            telefono TEXT,
            kilometraje REAL,
            kilometraje_limite REAL,
            mensaje_enviado BOOLEAN DEFAULT 0,
            fecha_envio TEXT
        )
    ''')
    conexion.commit()
    conexion.close()

def sincronizar_con_base_de_datos():
    try:
        df = pd.read_excel(excel_path_global, engine="openpyxl")
        df = df.rename(columns={
            "PLACA": "placa",
            "FECHA_ULTIMO_CAMBIO": "fecha_ultimo_cambio",
            "NOMBRE": "nombre",
            "TELEFONO": "telefono",
            "KILOMETRAJE": "kilometraje",
            "PROXIMO KILOMETRAJE": "kilometraje_limite"
        })
        df["fecha_ultimo_cambio"] = pd.to_datetime(df["fecha_ultimo_cambio"], dayfirst=True, errors='coerce')
        df = df.dropna(subset=["fecha_ultimo_cambio"])

        conexion = sqlite3.connect("programa_mensajes.db")
        cursor = conexion.cursor()

        nuevos = 0
        actualizados = 0

        for _, row in df.iterrows():
            placa = row["placa"]
            fecha = row["fecha_ultimo_cambio"].strftime("%Y-%m-%d")

            cursor.execute('''SELECT * FROM mensajes WHERE placa = ? AND fecha_ultimo_cambio = ?''', (placa, fecha))
            resultado = cursor.fetchone()

            telefono = str(row["telefono"]).strip()
            if not telefono.isdigit():
            	telefono = ""

            if resultado:
                actualizados += 1
                cursor.execute('''UPDATE mensajes 
                                  SET nombre = ?, telefono = ?, kilometraje = ?, kilometraje_limite = ?
                                  WHERE placa = ? AND fecha_ultimo_cambio = ?''',
                               (row["nombre"], telefono, row["kilometraje"], row["kilometraje_limite"], row["placa"], row["fecha_ultimo_cambio"].strftime("%Y-%m-%d")))
            else:
                nuevos += 1
                cursor.execute('''INSERT INTO mensajes (placa, fecha_ultimo_cambio, nombre, telefono, kilometraje, kilometraje_limite, mensaje_enviado)
                                  VALUES (?, ?, ?, ?, ?, ?, 0)''',
                               (row["placa"], row["fecha_ultimo_cambio"].strftime("%Y-%m-%d"), row["nombre"], telefono, row["kilometraje"], row["kilometraje_limite"]))

        conexion.commit()
        conexion.close()

        print(f"Sincronización completada. Nuevos registros: {nuevos}, Actualizados: {actualizados}")

        actualizar_tabla()
        mostrar_proximos()

    except Exception as e:
        print(f"Error durante la sincronización: {e}")

class ExcelChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(excel_path_global):
            print(f"Cambio detectado en {event.src_path}. Sincronizando...")
            time.sleep(5)  # Esperar para asegurar que el archivo esté accesible
            sincronizar_con_base_de_datos()  # Llamar la función de sincronización
            actualizar_tabla()  # Actualizar la tabla de la GUI
            mostrar_proximos()  # Actualizar la lista de próximos clientes

def obtener_pendientes():
    conexion = sqlite3.connect("programa_mensajes.db")
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM mensajes WHERE mensaje_enviado = 0")
    pendientes = cursor.fetchall()
    conexion.close()
    return pendientes

def marcar_como_enviado(id_registro):
    conexion = sqlite3.connect("programa_mensajes.db")
    cursor = conexion.cursor()
    cursor.execute('''UPDATE mensajes SET mensaje_enviado = 1, fecha_envio = ? WHERE id = ?''', 
                   (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), id_registro))
    conexion.commit()
    conexion.close()
    actualizar_tabla()

def enviar_mensajes_whatsapp(numero, mensaje):
    try:
        url = f"https://web.whatsapp.com/send?phone={numero}&text={mensaje}"
        web.open(url)
        time.sleep(20)
        pg.press('enter')
        time.sleep(10)
        print(f"Mensaje enviado a {numero}.")
                
        return True
    except Exception as e:
        print(f"Error al enviar mensaje: {e}")
        return False

envio_en_proceso = threading.Lock()


def verificar_y_enviar():
    pendientes = obtener_pendientes()
    for registro in pendientes:
        id_registro, placa, fecha_cambio, nombre, telefono, kilometraje, kilometraje_limite, _, _ = registro

        # Validar datos clave
        if not telefono or not nombre or not placa:
            print(f"❌ Registro inválido: {registro}")
            continue

        try:
            fecha_cambio_dt = datetime.strptime(fecha_cambio, "%Y-%m-%d")
        except Exception as e:
            print(f"❌ Error en la fecha del registro {id_registro}: {e}")
            continue

        dias_desde_cambio = (datetime.now() - fecha_cambio_dt).days

        if dias_desde_cambio >= 120:
            if kilometraje and kilometraje_limite:
                kilometraje_formateado = f"{kilometraje:,.0f}".replace(",", ".")
                kilometraje_limite_formateado = f"{kilometraje_limite:,.0f}".replace(",", ".")
                mensaje = (f"Estimado(a) Cliente,  \n"
                           f"El día {fecha_cambio_dt.strftime('%d/%m/%Y')} se realizó el cambio de aceite en tu vehículo \n"
                           f"de placa {placa} con {kilometraje_formateado} kilómetros. \n"
                           f"Si ya superaste los {kilometraje_limite_formateado} kilómetros, ¡es hora de cambiar el aceite y los filtros! \n"
                           f"¡Agenda tu cita hoy en Lubri-Servicios Baranoa! \ud83d\ude97\ud83c\udf1f \n"
                           f"\n¡Gracias por elegirnos!")
            else:
                mensaje = (f"Estimado(a) Cliente,  \n"
                           f"El día {fecha_cambio_dt.strftime('%d/%m/%Y')} se realizó el cambio de aceite en tu vehículo \n"
                           f"de placa {placa}. \n"
                           f"¡Recuerda realizar el mantenimiento preventivo a tiempo! \n"
                           f"¡Agenda tu cita hoy en Lubri-Servicios Baranoa! \ud83d\ude97\ud83c\udf1f \n"
                           f"\n¡Gracias por elegirnos!")

            # 🔒 Bloqueo para evitar múltiples envíos simultáneos
            if envio_en_proceso.acquire(timeout=30):
                resultado = enviar_mensajes_whatsapp(telefono, mensaje)
                if resultado:
                    marcar_como_enviado(id_registro)
                    actualizar_tabla()
                    mostrar_proximos()
                    pg.hotkey('ctrl', 'w')  # Cierra la pestaña de WhatsApp
                envio_en_proceso.release()
            else:
                print("⏳ Esperando para enviar el siguiente mensaje...")


# Programar el envío de mensajes todos los días a las 10:00 AM
#schedule.every().day.at("21:21").do(verificar_y_enviar)

def calcular_proximos():
    """Calcula los registros próximos a enviar mensajes."""
    pendientes = obtener_pendientes()
    proximos = []
    ahora = datetime.now()
    for registro in pendientes:
        fecha_cambio_dt = datetime.strptime(registro[2], "%Y-%m-%d")
        dias_pendientes = 120 - (ahora - fecha_cambio_dt).days
        proximos.append((registro[1], registro[3], max(0, dias_pendientes)))
    proximos.sort(key=lambda x: x[2])
    return proximos

# GUI
inicializar_db()

# Ventana de la GUI
root = ctk.CTk()
root.title("Gestión de Mensajes WhatsApp")
root.geometry("1200x800")

# Pestañas principales
tabview = ctk.CTkTabview(root)
tabview.pack(expand=True, fill="both")

# Pestañas para diferentes funcionalidades
tab_monitoreo = tabview.add("Monitoreo")
tab_configuracion = tabview.add("Configuración")
tab_proximos = tabview.add("Próximos Clientes")
tab_citas = tabview.add("📋 Citas Agendadas")

filtro_frame = ctk.CTkFrame(tab_monitoreo)
filtro_frame.pack(side="top", fill="x", padx=10, pady=5)

search_var = ctk.StringVar()

def filtrar_tabla(*args):
    """Filtra la tabla en base al texto de búsqueda."""
    texto = search_var.get().lower()
    for row in tabla_pendientes.get_children():
        tabla_pendientes.delete(row)

    conexion = sqlite3.connect("programa_mensajes.db")
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM mensajes")
    registros = cursor.fetchall()
    conexion.close()

    for registro in registros:
        placa = registro[1]
        nombre = registro[3]

        placa_str = placa if placa is not None else ""
        nombre_str = nombre if nombre is not None else ""

        if texto in placa_str.lower() or texto in nombre_str.lower():
            estado = "Enviado" if registro[7] else "Pendiente"
            tabla_pendientes.insert(
                "", "end",
                values=(placa_str, nombre_str, registro[4], registro[5], registro[2], estado)
            )

search_var.trace_add("write", filtrar_tabla)

search_label = ctk.CTkLabel(filtro_frame, text="Buscar por Placa o Nombre: ")
search_label.pack(side="left", padx=5)

search_entry = ctk.CTkEntry(filtro_frame, textvariable=search_var)
search_entry.pack(side="left", fill="x", expand=True, padx=5)

# Tabla en la pestaña de Monitoreo
tabla_pendientes = ttk.Treeview(tab_monitoreo, columns=("Placa", "Nombre", "Telefono", "Kilometraje", "Fecha", "Estado"), show="headings")
for col in ("Placa", "Nombre", "Telefono", "Kilometraje", "Fecha", "Estado"):
    tabla_pendientes.heading(col, text=col)
    tabla_pendientes.column(col, width=150, anchor="center")

tabla_pendientes.pack(expand=True, fill="both")

# Crear un frame para KPIs
kpi_frame = ctk.CTkFrame(tab_monitoreo)
kpi_frame.pack(side="top", fill="x", padx=10, pady=10)

# Etiquetas para mostrar KPIs
label_total = ctk.CTkLabel(kpi_frame, text="Total registros: 0")
label_enviados = ctk.CTkLabel(kpi_frame, text="Mensajes enviados: 0")
label_pendientes = ctk.CTkLabel(kpi_frame, text="Mensajes pendientes: 0")
label_exito = ctk.CTkLabel(kpi_frame, text="% Éxito: 0%")
label_total.grid(row=0, column=0, padx=10, pady=5)
label_enviados.grid(row=0, column=1, padx=10, pady=5)
label_pendientes.grid(row=0, column=2, padx=10, pady=5)
label_exito.grid(row=0, column=3, padx=10, pady=5)

# Crear figura para gráfico
fig = Figure(figsize=(4, 2))
ax = fig.add_subplot(111)
kpi_canvas = FigureCanvasTkAgg(fig, master=kpi_frame)
kpi_canvas.get_tk_widget().grid(row=1, columnspan=4, padx=10, pady=10)

def actualizar_kpis():
    """Calcula KPIs básicos y actualiza labels y gráfico."""
    conexion = sqlite3.connect("programa_mensajes.db")
    cursor = conexion.cursor()
    cursor.execute("SELECT COUNT(*) FROM mensajes")  
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM mensajes WHERE mensaje_enviado = 1")  
    enviados = cursor.fetchone()[0]
    pendientes = total - enviados
    exito = (enviados / total * 100) if total > 0 else 0
    conexion.close()

    label_total.configure(text=f"Total registros: {total}")
    label_enviados.configure(text=f"Mensajes enviados: {enviados}")
    label_pendientes.configure(text=f"Mensajes pendientes: {pendientes}")
    label_exito.configure(text=f"% Éxito: {exito:.2f}%")

    # Limpiar gráfico y actualizar
    ax.clear()
    ax.bar(["Enviados", "Pendientes"], [enviados, pendientes], color=["green", "red"])
    ax.set_title("Mensajes enviados vs pendientes")
    kpi_canvas.draw()

def actualizar_tabla():
    """Actualiza la tabla de monitoreo con los registros pendientes."""
    # Limpiar la tabla antes de actualizar
    for row in tabla_pendientes.get_children():
        tabla_pendientes.delete(row)

    # Cargar los registros de la base de datos
    conexion = sqlite3.connect("programa_mensajes.db")
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM mensajes ORDER BY id DESC LIMIT 100")
    registros = cursor.fetchall()
    conexion.close()

    actualizar_kpis()

    # Insertar los registros actualizados en la tabla
    for registro in registros:
        estado = "Enviado" if registro[7] else "Pendiente"
        tabla_pendientes.insert("", "end", values=(registro[1], registro[3], registro[4], registro[5], registro[2], estado))




# Botón para cargar un archivo Excel
def cargar_excel():
    file_path = filedialog.askopenfilename(filetypes=[("Archivos Excel", "*.xlsx *.xlsm")])
    if file_path:
        sincronizar_con_base_de_datos()
        actualizar_tabla()
        mostrar_proximos()

boton_cargar = ctk.CTkButton(tab_configuracion, text="Cargar Excel", command=cargar_excel)
boton_cargar.pack(pady=10)





# Sección de Próximos Clientes
canvas = ctk.CTkCanvas(tab_proximos, bg="black")
canvas.pack(side="left", expand=True, fill="both")

scrollbar_y = Scrollbar(tab_proximos, orient="vertical", command=canvas.yview)
scrollbar_y.pack(side="right", fill="y")

frame_scrollable = ctk.CTkFrame(canvas, fg_color="transparent")
frame_scrollable.grid_columnconfigure(0, weight=1)
canvas.create_window((0, 0), window=frame_scrollable, anchor="nw")
canvas.configure(yscrollcommand=scrollbar_y.set)



def mostrar_proximos():
    """Muestra los clientes próximos a vencer en el mantenimiento."""
    # Limpiar los widgets anteriores en el frame
    for widget in frame_scrollable.winfo_children():
        try:
            widget.destroy()
        except Exception as e:
            print(f"Error al destruir widget: {e}")

    # Calcular los próximos clientes a enviar mensajes
    proximos = calcular_proximos()

    # Asegúrate de que el frame sigue existiendo antes de crear nuevos widgets
    if frame_scrollable.winfo_exists():
        for placa, nombre, dias in proximos:
            try:
                texto = f"Placa: {placa}, Nombre: {nombre}, Días restantes: {dias}"
                ctk.CTkLabel(frame_scrollable, text=texto).pack(pady=5)
            except Exception as e:
                print(f"Error al crear widget: {e}")

        # Después de agregar los widgets, actualiza el frame
        frame_scrollable.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
    else:
        print("Error: El frame donde se deben agregar los próximos clientes no existe.")

# Botón para actualizar la sección de Próximos Clientes
boton_actualizar_proximos = ctk.CTkButton(tab_proximos, text="Actualizar Próximos", command=mostrar_proximos)
boton_actualizar_proximos.pack(pady=10)

# Programador de tareas automáticas
# Programador de tareas automáticas
envios_activos = False  # Asegúrate de definir esta variable al inicio del archivo

def iniciar_programador():
    global envios_activos
    while envios_activos:
        ahora = datetime.now()

        # Verifica si es la hora para enviar los mensajes
        hora_programada = ahora.replace(hour=10, minute=52, second=0, microsecond=0)

        # Si ya pasó la hora programada, o es el mismo día
        if ahora >= hora_programada:
            # Verifica si han pasado los 120 días desde el último cambio para los clientes
            verificar_y_enviar()

        # Espera 30 segundos antes de volver a verificar
        time.sleep(30)

def iniciar_envios():
    global envios_activos
    if not envios_activos:
        envios_activos = True
        threading.Thread(target=iniciar_programador, daemon=True).start()
        programador_label.configure(text="Programador activo", text_color="green")

def detener_envios():
    global envios_activos
    if envios_activos:
        envios_activos = False
        programador_label.configure(text="Programador detenido", text_color="red")

# Etiqueta para el estado del programador
programador_label = ctk.CTkLabel(tab_configuracion, text="Programador inactivo", text_color="red")
programador_label.pack(pady=10)

# Botones para controlar el programador
boton_iniciar_programador = ctk.CTkButton(tab_configuracion, text="Iniciar Programador", command=iniciar_envios)
boton_iniciar_programador.pack(pady=10)

boton_detener_programador = ctk.CTkButton(tab_configuracion, text="Detener Programador", command=detener_envios)
boton_detener_programador.pack(pady=10)



thread = threading.Thread(target=iniciar_programador, daemon=True)
thread.start()


def carga_automatica_y_activacion():
    try:
        print("Cargando y sincronizando Excel automáticamente...")
        sincronizar_con_base_de_datos()
        actualizar_tabla()
        mostrar_proximos()
        iniciar_envios()
    except Exception as e:
        print(f"No se pudo cargar el Excel automáticamente: {e}")



# Actualizaciones automáticas de tablas
root.after(5000, actualizar_tabla)
root.after(10000, mostrar_proximos)

# Configuración del observador de cambios
event_handler = ExcelChangeHandler()
observer = Observer()
observer.schedule(event_handler, path=".", recursive=False)
observer.start()

carga_automatica_y_activacion()


# Lanzamos Flask en segundo plano

def anunciar(texto):
    engine = pyttsx3.init()
    engine.setProperty('rate', 160)  # velocidad de habla
    engine.setProperty('volume', 4.0)
    engine.say(texto)
    engine.runAndWait()

def iniciar_flask_agendamiento():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    DB = "programa_mensajes.db"
    PDF_DIR = "citas"
    os.makedirs(PDF_DIR, exist_ok=True)

    def init_db():
        with sqlite3.connect(DB) as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS citas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT,
                    cedula TEXT,
                    telefono TEXT,
                    placa TEXT,
                    marca TEXT,
                    modelo TEXT,
                    fecha TEXT,
                    hora TEXT,
                    estado TEXT DEFAULT 'Pendiente',
                    fecha_registro TEXT
                )
            """)
            conn.commit()

    @app.route("/disponibilidad")
    def disponibilidad():
        dia = request.args.get("fecha")
        with sqlite3.connect(DB) as conn:
            c = conn.cursor()
            c.execute("SELECT hora FROM citas WHERE fecha = ?", (dia,))
            ocupadas = [r[0] for r in c.fetchall()]
        return jsonify({"ocupadas": ocupadas})

    @app.route("/agendar", methods=["POST"])
    def agendar():
        datos = request.json
        nombre = datos["nombre"]
        cedula = datos["cedula"]
        telefono = datos["telefono"]
        placa = datos["placa"]
        marca = datos["marca"]
        modelo = datos["modelo"]
        fecha = datos["fecha"]
        hora = datos["hora"]
        fecha_registro = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with sqlite3.connect(DB) as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM citas WHERE fecha=? AND hora=?", (fecha, hora))
            if c.fetchone():
                return jsonify({"status": "ocupado"}), 409

            c.execute("""
                INSERT INTO citas (nombre, cedula, telefono, placa, marca, modelo, fecha, hora, fecha_registro)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (nombre, cedula, telefono, placa, marca, modelo, fecha, hora, fecha_registro))
            conn.commit()

        archivo = generar_pdf(nombre, cedula, telefono, placa, marca, modelo, fecha, hora)
        anunciar("Nueva cita agendada para " + nombre)
        return jsonify({"status": "ok", "pdf_url": f"/pdf/{archivo}"})

    @app.route("/pdf/<nombre_archivo>")
    def descargar_pdf(nombre_archivo):
        ruta_pdf = os.path.join("citas", nombre_archivo)
        if not os.path.exists(ruta_pdf):
            return f"Archivo no encontrado: {ruta_pdf}", 404
        return send_file(ruta_pdf, as_attachment=True)

    def generar_pdf(nombre, cedula, telefono, placa, marca, modelo, fecha, hora):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        pdf.cell(200, 10, txt="Lubri-Servicios Baranoa - Confirmación de Cita", ln=True, align='C')
        pdf.ln(10)
        pdf.cell(200, 10, txt=f"Nombre: {nombre}", ln=True)
        pdf.cell(200, 10, txt=f"Cédula: {cedula}", ln=True)
        pdf.cell(200, 10, txt=f"Teléfono: {telefono}", ln=True)
        pdf.cell(200, 10, txt=f"Vehículo: {marca} {modelo} - {placa}", ln=True)
        pdf.cell(200, 10, txt=f"Fecha: {fecha} a las {hora}", ln=True)
        pdf.ln(5)
        pdf.multi_cell(0, 10, txt="Términos y condiciones:\n- Llegue 10 minutos antes.\n- Cancelaciones deben hacerse 24h antes.\n- No asistir sin aviso puede afectar futuras reservas.")
        pdf.ln(5)
        pdf.cell(200, 10, txt=f"Emitido: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)

        archivo = f"{placa}_{fecha}_{hora.replace(':', '')}.pdf"
        ruta = os.path.join(PDF_DIR, archivo)
        pdf.output(ruta)
        return archivo    

    @app.route("/")
    def formulario_cliente():
        return render_template("index.html")

    app.run(debug=False, port=5000)

    init_db()
    app.run(port=5000)



# Lanzamos el servidor Flask embebido
threading.Thread(target=iniciar_flask_agendamiento, daemon=True).start()

# Creamos la interfaz principal
ventana = ctk.CTk()
ventana.title("Gestor de Citas Lubri-Servicios")
ventana.geometry("900x600")
tabs = ctk.CTkTabview(ventana)
tabs.pack(expand=True, fill="both")



cols = ("ID", "Nombre", "Cédula", "Teléfono", "Placa", "Marca", "Modelo", "Fecha", "Hora", "Estado")
tabla = ttk.Treeview(tab_citas, columns=cols, show="headings")
for col in cols:
    tabla.heading(col, text=col)
    tabla.column(col, width=100)
tabla.pack(expand=True, fill="both", pady=10)

btn_frame = ctk.CTkFrame(tab_citas)
btn_frame.pack(pady=5)

actualizar_btn = ctk.CTkButton(btn_frame, text="🔄 Actualizar", command=lambda: cargar_citas(tabla))
actualizar_btn.grid(row=0, column=0, padx=5)

marcar_btn = ctk.CTkButton(btn_frame, text="✅ Marcar como Cumplida", command=lambda: actualizar_estado(tabla, "Cumplida"))
marcar_btn.grid(row=0, column=1, padx=5)

cancelar_btn = ctk.CTkButton(btn_frame, text="❌ Cancelar Cita", command=lambda: actualizar_estado(tabla, "Cancelada"))
cancelar_btn.grid(row=0, column=2, padx=5)

ver_pdf_btn = ctk.CTkButton(btn_frame, text="📄 Ver PDF", command=lambda: abrir_pdf(tabla))
ver_pdf_btn.grid(row=0, column=3, padx=5)

abrir_web_btn = ctk.CTkButton(btn_frame, text="🌐 Ver Formulario Web", command=lambda: web.open("http://127.0.0.1:5000"))
abrir_web_btn.grid(row=0, column=4, padx=5)

# Funciones para gestionar citas

def cargar_citas(tree):
    tree.delete(*tree.get_children())
    with sqlite3.connect("programa_mensajes.db") as conn:
        c = conn.cursor()
        c.execute("SELECT id, nombre, cedula, telefono, placa, marca, modelo, fecha, hora, estado FROM citas ORDER BY fecha, hora")
        for row in c.fetchall():
            tree.insert("", "end", values=row)

def actualizar_estado(tree, nuevo_estado):
    item = tree.focus()
    if not item:
        return
    valores = tree.item(item, "values")
    id_cita = valores[0]
    with sqlite3.connect("programa_mensajes.db") as conn:
        c = conn.cursor()
        c.execute("UPDATE citas SET estado=? WHERE id=?", (nuevo_estado, id_cita))
        conn.commit()
    cargar_citas(tree)
    anunciar(f"Cita {nuevo_estado.lower()} correctamente")

def abrir_pdf(tree):
    item = tree.focus()
    if not item:
        return
    valores = tree.item(item, "values")
    archivo = f"{valores[4]}_{valores[7]}_{valores[8].replace(':', '')}.pdf"
    ruta = os.path.join("citas", archivo)
    if os.path.exists(ruta):
        os.startfile(ruta)

# Carga inicial de citas
cargar_citas(tabla)


# Ejecución de la GUI
try:
    root.mainloop()
    ventana.mainloop()
    
except KeyboardInterrupt:
    observer.stop()
observer.join()


