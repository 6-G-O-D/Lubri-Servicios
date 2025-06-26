// 🔧 script.js completo y corregido para vista previa, generación de enlace y descarga PDF

const pasos = document.querySelectorAll('.step');
const secciones = document.querySelectorAll('.step-content');
const siguienteBtns = document.querySelectorAll('.next-btn');
const atrasBtns = document.querySelectorAll('.back-btn');
let pasoActual = 0;

function mostrarPaso(paso) {
  pasos.forEach((p, i) => p.classList.toggle('active', i === paso));
  secciones.forEach((s, i) => s.classList.toggle('active', i === paso));
}

siguienteBtns.forEach(btn => btn.addEventListener('click', () => {
  if (pasoActual === 1) mostrarVistaPrevia();
  if (pasoActual === 2) enviarFormulario();

  if (pasoActual < pasos.length - 1) {
    pasoActual++;
    mostrarPaso(pasoActual);
  }
}));

atrasBtns.forEach(btn => btn.addEventListener('click', () => {
  if (pasoActual > 0) {
    pasoActual--;
    mostrarPaso(pasoActual);
  }
}));

function mostrarVistaPrevia() {
  const nombre = document.getElementById('nombre').value;
  const cedula = document.getElementById('cedula').value;
  const telefono = document.getElementById('telefono').value;
  const placa = document.getElementById('placa').value;
  const marca = document.getElementById('marca').value;
  const modelo = document.getElementById('modelo').value;
  const fecha = document.getElementById('fecha').value;
  const hora = document.querySelector('select[name="hora"]')?.value;

  if (!fecha || !hora) {
    alert("Por favor selecciona una fecha y hora disponible.");
    pasoActual = 1;
    mostrarPaso(pasoActual);
    return;
  }

  const vista = `
    <strong>Nombre:</strong> ${nombre}<br>
    <strong>Cédula:</strong> ${cedula}<br>
    <strong>Teléfono:</strong> ${telefono}<br>
    <strong>Vehículo:</strong> ${marca} ${modelo} <em>(${placa})</em><br>
    <strong>Fecha:</strong> ${fecha}<br>
    <strong>Hora:</strong> ${hora}
  `;

  document.getElementById('vista-previa').innerHTML = vista;
}

function enviarFormulario() {
  const nombre = document.getElementById('nombre').value;
  const cedula = document.getElementById('cedula').value;
  const telefono = document.getElementById('telefono').value;
  const placa = document.getElementById('placa').value;
  const marca = document.getElementById('marca').value;
  const modelo = document.getElementById('modelo').value;
  const fecha = document.getElementById('fecha').value;
  const hora = document.querySelector('select[name="hora"]')?.value;

  const datos = { nombre, cedula, telefono, placa, marca, modelo, fecha, hora };

  fetch('/agendar', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(datos)
  })
    .then(res => res.json())
    .then(data => {
      if (data.status === 'ok') {
        const link = location.origin + data.pdf_url;
        document.getElementById('enlaceCita').value = link;

        const btn = document.createElement('a');
        btn.href = link;
        btn.textContent = '📥 Descargar comprobante PDF';
        btn.className = 'next-btn glow-box';
        btn.target = '_blank';
        btn.style.display = 'inline-block';
        btn.style.marginTop = '15px';

        document.getElementById('enlaceCita').insertAdjacentElement('afterend', btn);
      }
    })
    .catch(err => console.error("Error al enviar cita:", err));
}

// Calendario y horas disponibles

const fechaInput = document.getElementById('fecha');
const selectHoras = document.getElementById('horas');

if (fechaInput) {
  const hoy = new Date().toISOString().split('T')[0];
  fechaInput.setAttribute('min', hoy);

  fechaInput.addEventListener('change', (e) => {
    const fecha = new Date(e.target.value);
    if (fecha.getDay() === 0) {
      alert("Los domingos no están disponibles. Por favor elige otro día.");
      e.target.value = '';
      selectHoras.innerHTML = '<option value="">Selecciona hora</option>';
    } else {
      cargarHorasDisponibles(e.target.value);
    }
  });
}

function cargarHorasDisponibles(fechaSeleccionada) {
  selectHoras.innerHTML = '<option value="">Selecciona hora</option>';
  const posiblesHoras = ['08:00 AM', '09:00 AM', '10:00 AM', '11:00 AM', '02:00 PM', '03:00 PM', '04:00 PM', '05:00 PM'];

  fetch(`/disponibilidad?fecha=${fechaSeleccionada}`)
    .then(res => res.json())
    .then(data => {
      posiblesHoras.forEach(hora => {
        if (!data.ocupadas.includes(hora)) {
          const option = document.createElement('option');
          option.value = hora;
          option.textContent = hora;
          selectHoras.appendChild(option);
        }
      });
    })
    .catch(err => console.error("Error cargando horas:", err));
}

// Corrección del cursor tipo texto en todo el cuerpo
document.body.style.cursor = "default";
