/**
 * ==========================================================================
 * SISTEMA ESCOLAR DE PUNTOS POR QR - LÓGICA PRINCIPAL (MOBILE-FIRST)
 * ==========================================================================
 */

// Configuración de Secciones y Puntos
const SECCIONES = {
  llegada: { nombre: 'Conteo de Llegada', puntos: 1, colorClass: 'llegada' },
  taller: { nombre: 'Taller', puntos: 3, colorClass: 'taller' },
  excursiones: { nombre: 'Excursiones', puntos: 4, colorClass: 'excursiones' },
  divulgacion: { nombre: 'Divulgación', puntos: 5, colorClass: 'divulgacion' }
};

// Estado Global de la Aplicación
const state = {
  isAuthenticated: false,
  activeSection: 'llegada',
  simulatedSchoolHours: true, // Habilitado por defecto para facilitar pruebas a cualquier hora
  isRealSchoolHours: false,
  pinBuffer: '',
  html5QrCode: null,
  isCameraRunning: false,
  isCameraStarting: false,
  currentCameraFacing: 'environment', // Prioridad cámara trasera en Android / iOS
  availableCameras: [],
  selectedCameraId: null,
  students: [],
  logs: [],
  serverInfo: null
};

// ==========================================================================
// SÍNTESIS DE AUDIO Y FEEDBACK HÁPTICO (NATIVO, SIN ARCHIVOS EXTERNOS)
// ==========================================================================
class SoundAndHaptics {
  constructor() {
    this.audioCtx = null;
  }

  _getAudioContext() {
    if (!this.audioCtx) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        this.audioCtx = new AudioContext();
      }
    }
    if (this.audioCtx && this.audioCtx.state === 'suspended') {
      this.audioCtx.resume();
    }
    return this.audioCtx;
  }

  playSuccess() {
    try {
      const ctx = this._getAudioContext();
      if (!ctx) return;
      const now = ctx.currentTime;

      // Doble tono ascendente armónico (éxito)
      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const gain = ctx.createGain();

      osc1.type = 'sine';
      osc2.type = 'sine';

      osc1.frequency.setValueAtTime(587.33, now); // D5
      osc1.frequency.exponentialRampToValueAtTime(880, now + 0.15); // A5

      osc2.frequency.setValueAtTime(880, now + 0.15);
      osc2.frequency.exponentialRampToValueAtTime(1174.66, now + 0.3); // D6

      gain.gain.setValueAtTime(0.2, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.35);

      osc1.connect(gain);
      osc2.connect(gain);
      gain.connect(ctx.destination);

      osc1.start(now);
      osc1.stop(now + 0.15);
      osc2.start(now + 0.15);
      osc2.stop(now + 0.35);
    } catch (e) {
      console.warn('Audio feedback error', e);
    }

    // Vibración corta de éxito (100ms)
    if (navigator.vibrate) {
      navigator.vibrate([100]);
    }
  }

  playDuplicate() {
    try {
      const ctx = this._getAudioContext();
      if (!ctx) return;
      const now = ctx.currentTime;

      // Doble tono grave de advertencia
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'triangle';
      osc.frequency.setValueAtTime(260, now);
      osc.frequency.setValueAtTime(220, now + 0.12);

      gain.gain.setValueAtTime(0.25, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.28);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(now);
      osc.stop(now + 0.28);
    } catch (e) {
      console.warn('Audio feedback error', e);
    }

    // Vibración doble de advertencia
    if (navigator.vibrate) {
      navigator.vibrate([180, 80, 180]);
    }
  }

  playClick() {
    try {
      const ctx = this._getAudioContext();
      if (!ctx) return;
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(700, now);
      osc.frequency.exponentialRampToValueAtTime(400, now + 0.04);

      gain.gain.setValueAtTime(0.08, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.04);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(now);
      osc.stop(now + 0.04);
    } catch (e) {
      // Silenciar
    }

    if (navigator.vibrate) {
      navigator.vibrate(20);
    }
  }
}

const feedback = new SoundAndHaptics();

// ==========================================================================
// CONTROL DE NAVEGACIÓN Y VISTAS
// ==========================================================================
function switchView(viewId) {
  const views = document.querySelectorAll('.view-section');
  views.forEach(v => v.classList.remove('active'));

  const target = document.getElementById(viewId);
  if (target) {
    target.classList.add('active');
  }

  // Si salimos del escáner, pausar cámara para ahorrar batería en móviles
  if (viewId !== 'view-scanner' && state.isCameraRunning) {
    stopCamera();
  }

  // Actualizar estado de la barra de navegación inferior
  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-view') === viewId);
  });

  // Si abrimos la vista de BBDD, refrescar registros
  if (viewId === 'view-database') {
    loadDatabaseData();
  }
}

// ==========================================================================
// COMPROBACIÓN DE HORARIO LECTIVO (L-V 08:00 A 14:30)
// ==========================================================================
async function checkScheduleStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    state.serverInfo = data;
    state.isRealSchoolHours = data.is_school_hours;

    // Actualizar reloj y badge
    document.getElementById('clock-display').textContent = data.current_time;
    document.getElementById('calendar-display').textContent = `${data.day_name}, ${data.current_date}`;

    const badge = document.getElementById('header-status-badge');
    const badgeText = document.getElementById('header-status-text');

    const isOpen = state.isRealSchoolHours || state.simulatedSchoolHours;

    if (isOpen) {
      badge.className = 'badge-status';
      badgeText.textContent = state.simulatedSchoolHours && !state.isRealSchoolHours ? 'Simulación Activa' : 'Horario Lectivo';
    } else {
      badge.className = 'badge-status closed';
      badgeText.textContent = 'Cerrado';
    }

    // Evaluar flujo de la web según el diagrama
    evaluateAppFlow();
  } catch (err) {
    console.error('Error comprobando estado del servidor:', err);
  }
}

function evaluateAppFlow() {
  const isSchoolOpen = state.isRealSchoolHours || state.simulatedSchoolHours;

  if (!isSchoolOpen) {
    // DIAGRAMA: HORARIO LECTIVO? NO -> CERRADO
    switchView('view-closed');
    document.getElementById('app-bottom-nav').style.display = 'none';
    document.getElementById('btn-logout').style.display = 'none';
    return;
  }

  // HORARIO LECTIVO? SI
  if (!state.isAuthenticated) {
    // DIAGRAMA: PEDIR LOGIN
    switchView('view-login');
    document.getElementById('app-bottom-nav').style.display = 'none';
    document.getElementById('btn-logout').style.display = 'none';
  } else {
    // DIAGRAMA: LOGIN CORRECT -> DESBLOQUEAR PÁGINA
    document.getElementById('app-bottom-nav').style.display = 'flex';
    document.getElementById('btn-logout').style.display = 'flex';
    
    // Si estaba en pantalla de cerrado o login, ir a selector de secciones
    const currentActive = document.querySelector('.view-section.active');
    if (!currentActive || currentActive.id === 'view-closed' || currentActive.id === 'view-login') {
      switchView('view-sections');
    }
  }
}

// ==========================================================================
// LOGIN POR PIN PAD (DOCENTE - CLAVE DEMO 0000)
// ==========================================================================
function updatePinDots() {
  const dots = document.querySelectorAll('#pin-dots .pin-dot');
  dots.forEach((dot, index) => {
    dot.classList.toggle('filled', index < state.pinBuffer.length);
    dot.classList.remove('error');
  });
}

function handlePinInput(key) {
  feedback.playClick();
  const pinMsg = document.getElementById('pin-message');
  pinMsg.textContent = '';
  pinMsg.classList.remove('error');

  if (key === 'clear') {
    state.pinBuffer = '';
    updatePinDots();
    return;
  }

  if (key === 'backspace') {
    state.pinBuffer = state.pinBuffer.slice(0, -1);
    updatePinDots();
    return;
  }

  if (state.pinBuffer.length < 4) {
    state.pinBuffer += key;
    updatePinDots();

    if (state.pinBuffer.length === 4) {
      // Validar PIN automáticamente al llegar a 4 dígitos
      verifyPin(state.pinBuffer);
    }
  }
}

async function verifyPin(pin) {
  try {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin })
    });

    const data = await res.json();

    if (data.ok) {
      // DIAGRAMA: LOGIN CORRECT = SI -> DESBLOQUEAR PÁGINA
      state.isAuthenticated = true;
      state.pinBuffer = '';
      updatePinDots();
      feedback.playSuccess();
      evaluateAppFlow();
    } else {
      // DIAGRAMA: LOGIN CORRECT = NO -> VOLVER A INTENTAR (HASTA CORRECTO)
      feedback.playDuplicate();
      const dotsContainer = document.getElementById('pin-dots');
      const dots = dotsContainer.querySelectorAll('.pin-dot');
      dots.forEach(d => d.classList.add('error'));
      dotsContainer.classList.add('shake');

      const pinMsg = document.getElementById('pin-message');
      pinMsg.textContent = 'Clave incorrecta. Vuelve a intentarlo.';
      pinMsg.classList.add('error');

      setTimeout(() => {
        dotsContainer.classList.remove('shake');
        state.pinBuffer = '';
        updatePinDots();
      }, 700);
    }
  } catch (err) {
    console.error('Error al verificar PIN:', err);
  }
}

// ==========================================================================
// SELECCIÓN DE SECCIÓN Y CONFIGURACIÓN DEL ESCÁNER
// ==========================================================================
function selectSection(sectionKey) {
  if (!SECCIONES[sectionKey]) return;
  state.activeSection = sectionKey;
  feedback.playClick();

  const cfg = SECCIONES[sectionKey];
  const banner = document.getElementById('scanner-banner');
  banner.className = `scan-active-banner ${cfg.colorClass}`;

  document.getElementById('active-section-name').textContent = cfg.nombre;
  document.getElementById('active-section-points').textContent = `(+${cfg.puntos} ${cfg.puntos === 1 ? 'pto' : 'ptos'})`;

  switchView('view-scanner');
  startCamera(); // Inicia la cámara automáticamente al entrar a escanear
}

// ==========================================================================
// CÁMARA Y ESCÁNER QR (HTML5-QRCODE CON ENUMERACIÓN ROBUSTA Y CONTROL DE ESTADOS)
// ==========================================================================

// Control de estados visuales del visor
function setScannerUiState(mode) {
  // mode: 'placeholder' | 'loading' | 'streaming' | 'error'
  const placeholder = document.getElementById('scanner-placeholder');
  const loading = document.getElementById('scanner-loading');
  const overlay = document.getElementById('scanner-overlay');
  const errorCard = document.getElementById('scanner-error');

  if (placeholder) placeholder.style.display = (mode === 'placeholder') ? 'flex' : 'none';
  if (loading) loading.style.display = (mode === 'loading') ? 'flex' : 'none';
  if (overlay) overlay.style.display = (mode === 'streaming') ? 'flex' : 'none';
  if (errorCard) errorCard.style.display = (mode === 'error') ? 'flex' : 'none';
}

function showScannerError(title, message, icon = '⚠️') {
  setScannerUiState('error');
  const titleEl = document.getElementById('scanner-error-title');
  const descEl = document.getElementById('scanner-error-desc');
  const iconEl = document.getElementById('scanner-error-icon');
  if (titleEl) titleEl.textContent = title;
  if (descEl) descEl.textContent = message;
  if (iconEl) iconEl.textContent = icon;
}

function isSecureContextForCamera() {
  return window.isSecureContext ||
    location.hostname === 'localhost' ||
    location.hostname === '127.0.0.1';
}

function checkInsecureContextNotice() {
  const banner = document.getElementById('insecure-context-banner');
  if (banner) {
    banner.style.display = (!isSecureContextForCamera()) ? 'flex' : 'none';
  }
}

async function loadAvailableCameras() {
  if (!window.Html5Qrcode) return [];
  try {
    const devices = await Html5Qrcode.getCameras();
    state.availableCameras = devices || [];
    updateCameraSelectDropdown();
    return state.availableCameras;
  } catch (err) {
    console.warn('No se pudieron listar las cámaras directamente (posible falta de permisos iniciales):', err);
    state.availableCameras = [];
    return [];
  }
}

function updateCameraSelectDropdown() {
  const select = document.getElementById('camera-select');
  const container = document.getElementById('camera-select-container');
  if (!select || !container) return;

  if (state.availableCameras.length > 1) {
    select.innerHTML = '';
    state.availableCameras.forEach((cam, idx) => {
      const opt = document.createElement('option');
      opt.value = cam.id;
      opt.textContent = cam.label || `Cámara ${idx + 1}`;
      if (cam.id === state.selectedCameraId) opt.selected = true;
      select.appendChild(opt);
    });
    container.style.display = 'flex';
  } else {
    container.style.display = 'none';
  }
}

async function initQrScanner() {
  if (!window.Html5Qrcode) {
    console.warn('Biblioteca Html5Qrcode no encontrada.');
    return;
  }

  if (!state.html5QrCode) {
    state.html5QrCode = new Html5Qrcode("reader");
  }
}

async function startCamera() {
  if (state.isCameraRunning || state.isCameraStarting) return;
  state.isCameraStarting = true;

  const btnToggle = document.getElementById('btn-toggle-camera');
  if (btnToggle) btnToggle.textContent = '⏳ Conectando...';

  // Mostrar indicador de carga en el visor
  setScannerUiState('loading');
  checkInsecureContextNotice();

  if (!state.html5QrCode) {
    await initQrScanner();
  }

  if (!state.html5QrCode) {
    state.isCameraStarting = false;
    if (btnToggle) btnToggle.textContent = '📷 Iniciar Cámara';
    showScannerError(
      'Biblioteca no disponible',
      'No se pudo inicializar la biblioteca de lectura de códigos QR. Recarga la página.'
    );
    return;
  }

  const config = {
    fps: 10,
    qrbox: { width: 220, height: 220 },
    aspectRatio: 1.0
  };

  try {
    // 1. Obtener lista de cámaras disponibles si aún no se han cargado
    if (state.availableCameras.length === 0) {
      await loadAvailableCameras();
    }

    let cameraSource = null;

    // A) Si el usuario ya eligió una cámara en el selector
    if (state.selectedCameraId) {
      cameraSource = state.selectedCameraId;
    } else if (state.availableCameras.length > 0) {
      // B) Si hay cámaras detectadas:
      // En móvil, buscar cámara trasera con regex
      if (state.currentCameraFacing === 'environment') {
        const backCam = state.availableCameras.find(c =>
          /back|rear|trasera|environment|posterior/i.test(c.label)
        );
        cameraSource = backCam ? backCam.id : state.availableCameras[state.availableCameras.length - 1].id;
      } else {
        const frontCam = state.availableCameras.find(c =>
          /front|user|delantera|facial/i.test(c.label)
        );
        cameraSource = frontCam ? frontCam.id : state.availableCameras[0].id;
      }
      state.selectedCameraId = cameraSource;
      updateCameraSelectDropdown();
    }

    // C) Si tenemos un cameraId (string), usarlo directamente
    if (cameraSource) {
      await state.html5QrCode.start(
        cameraSource,
        config,
        onScanSuccess,
        onScanFailure
      );
    } else {
      // D) Fallback usando facingMode simple (string directo, nunca objeto con ideal)
      try {
        await state.html5QrCode.start(
          { facingMode: state.currentCameraFacing },
          config,
          onScanSuccess,
          onScanFailure
        );
      } catch (errFacing) {
        console.warn('Fallback: probando modo user o cámara por defecto...', errFacing);
        await state.html5QrCode.start(
          { facingMode: "user" },
          config,
          onScanSuccess,
          onScanFailure
        );
      }
    }

    // Éxito: Visor encendido y funcionando
    state.isCameraRunning = true;
    state.isCameraStarting = false;
    setScannerUiState('streaming');
    if (btnToggle) btnToggle.textContent = '⏹️ Pausar Cámara';

    // Una vez otorgados los permisos por el usuario, refrescar lista de cámaras para mostrar nombres reales
    if (state.availableCameras.length === 0 || !state.availableCameras[0].label) {
      await loadAvailableCameras();
    }

  } catch (err) {
    console.error('Error al acceder a la cámara:', err);
    state.isCameraRunning = false;
    state.isCameraStarting = false;
    if (btnToggle) btnToggle.textContent = '📷 Iniciar Cámara';

    const errStr = String(err).toLowerCase();
    if (errStr.includes('permission') || errStr.includes('denied') || errStr.includes('notallowed')) {
      showScannerError(
        'Permiso de Cámara Denegado',
        'El navegador no tiene permiso para usar la cámara. Haz clic en el icono del candado en la barra de direcciones de tu navegador y permite el acceso a la cámara.',
        '🚫'
      );
    } else if (errStr.includes('notfound') || errStr.includes('devicesnotfound') || errStr.includes('no camera')) {
      showScannerError(
        'Cámara No Encontrada',
        'No se detectó ninguna cámara o webcam en este equipo. Conecta un dispositivo de video o usa el botón "Hacer Foto QR".',
        '📷'
      );
    } else if (errStr.includes('secure') || errStr.includes('insecure') || !isSecureContextForCamera()) {
      showScannerError(
        'Conexión No Segura (HTTP)',
        'Los navegadores móviles bloquean el visor de video en directo en redes locales sin HTTPS. Puedes usar el botón "📸 Hacer Foto QR" para capturar el carnet al instante.',
        '🔒'
      );
    } else if (errStr.includes('in use') || errStr.includes('readable') || errStr.includes('notreadable') || errStr.includes('busy')) {
      showScannerError(
        'Cámara Ocupada',
        'La cámara está siendo utilizada por otra aplicación (Zoom, Teams, etc.). Ciérrala y reintenta.',
        '⚠️'
      );
    } else {
      showScannerError(
        'No se pudo activar la cámara',
        `No fue posible iniciar el sensor de video (${err.message || err}). Puedes usar el botón "📸 Foto QR" para escanear con la cámara nativa sin restricciones.`,
        '⚠️'
      );
    }
  }
}

async function stopCamera() {
  if (state.html5QrCode && (state.isCameraRunning || state.isCameraStarting)) {
    try {
      await state.html5QrCode.stop();
    } catch (e) {
      console.warn('Error al detener cámara:', e);
    }
    state.isCameraRunning = false;
    state.isCameraStarting = false;
    setScannerUiState('placeholder');
    const btnToggle = document.getElementById('btn-toggle-camera');
    if (btnToggle) btnToggle.textContent = '📷 Iniciar Cámara';
  }
}

async function flipCamera() {
  if (state.availableCameras.length > 1) {
    const currentIndex = state.availableCameras.findIndex(c => c.id === state.selectedCameraId);
    const nextIndex = (currentIndex + 1) % state.availableCameras.length;
    state.selectedCameraId = state.availableCameras[nextIndex].id;
    updateCameraSelectDropdown();
  } else {
    state.currentCameraFacing = (state.currentCameraFacing === 'environment') ? 'user' : 'environment';
  }

  if (state.isCameraRunning) {
    await stopCamera();
    await startCamera();
  }
}

// Callback de lectura exitosa del escáner
let lastScanTime = 0;
async function onScanSuccess(decodedText) {
  const now = Date.now();
  // Debounce para evitar lecturas continuas accidentales en menos de 1.5s
  if (now - lastScanTime < 1500) return;
  lastScanTime = now;

  processScan(decodedText);
}

function onScanFailure(error) {
  // Ignorar errores de frames sin QR para no saturar consola
}

// ==========================================================================
// PROCESAMIENTO DE ESCANEO Y GUARDADO EN BBDD SQLITE
// ==========================================================================
async function processScan(pseudonimo) {
  try {
    const res = await fetch('/api/escanear', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pseudonimo: pseudonimo.trim().toUpperCase(),
        seccion: state.activeSection,
        simulated: state.simulatedSchoolHours
      })
    });

    const data = await res.json();

    if (data.ok) {
      // ÉXITO: Puntos otorgados y guardados en BBDD
      feedback.playSuccess();
      showFeedbackModal({
        type: 'success',
        title: '¡Puntos Asignados!',
        desc: `<strong>+${data.alumno.puntos_ganados} pts</strong> asignados a <strong>${data.alumno.pseudonimo}</strong> (${data.alumno.alias}) en <em>${data.seccion}</em>.<br><br>Puntos totales acumulados: <strong>${data.alumno.total_puntos} pts</strong>.`
      });
      loadDatabaseData(); // Refrescar BBDD en segundo plano
    } else {
      // ERROR / DUPLICADO / FUERA DE HORARIO
      feedback.playDuplicate();
      if (data.error_code === 'ALREADY_SCANNED') {
        showFeedbackModal({
          type: 'duplicate',
          title: 'Registro Ya Realizado',
          desc: data.message
        });
      } else {
        showFeedbackModal({
          type: 'error',
          title: 'No Permitido',
          desc: data.message
        });
      }
    }
  } catch (err) {
    console.error('Error procesando escaneo:', err);
    showFeedbackModal({
      type: 'error',
      title: 'Error de Conexión',
      desc: 'No se pudo conectar con la base de datos del servidor.'
    });
  }
}

// Feedback Modal
function showFeedbackModal({ type, title, desc }) {
  const modal = document.getElementById('scan-feedback-modal');
  const icon = document.getElementById('feedback-icon');
  const titleEl = document.getElementById('feedback-title');
  const descEl = document.getElementById('feedback-desc');

  icon.className = `feedback-icon ${type}`;
  if (type === 'success') icon.textContent = '🎉';
  else if (type === 'duplicate') icon.textContent = '⚠️';
  else icon.textContent = '✕';

  titleEl.textContent = title;
  descEl.innerHTML = desc;

  modal.classList.add('show');
}

function hideFeedbackModal() {
  document.getElementById('scan-feedback-modal').classList.remove('show');
}

// ==========================================================================
// ALUMNOS DEMO Y GENERADOR DE CÓDIGOS QR
// ==========================================================================
async function loadStudentsAndDemoChips() {
  try {
    const res = await fetch('/api/alumnos');
    const data = await res.json();
    state.students = data.alumnos || [];

    const container = document.getElementById('demo-chips-container');
    container.innerHTML = '';

    state.students.forEach(alumno => {
      const chip = document.createElement('div');
      chip.className = 'student-chip';
      chip.innerHTML = `
        <span class="chip-alias">${alumno.alias}</span>
        <span class="chip-pseudonym">${alumno.pseudonimo}</span>
        <div class="chip-actions">
          <button class="btn-chip scan-now" data-pseudonimo="${alumno.pseudonimo}" title="Escanear alumno en sección actual">
            ⚡ Escanear
          </button>
          <button class="btn-chip view-qr" data-pseudonimo="${alumno.pseudonimo}" data-alias="${alumno.alias}" title="Ver código QR para apuntar cámara">
            QR
          </button>
        </div>
      `;
      container.appendChild(chip);
    });

    // Eventos de los chips demo
    container.querySelectorAll('.scan-now').forEach(btn => {
      btn.addEventListener('click', () => {
        const pseudonimo = btn.getAttribute('data-pseudonimo');
        processScan(pseudonimo);
      });
    });

    container.querySelectorAll('.view-qr').forEach(btn => {
      btn.addEventListener('click', () => {
        const pseudonimo = btn.getAttribute('data-pseudonimo');
        const alias = btn.getAttribute('data-alias');
        openStudentQrModal(pseudonimo, alias);
      });
    });

  } catch (err) {
    console.error('Error cargando alumnos:', err);
  }
}

function openStudentQrModal(pseudonimo, alias) {
  document.getElementById('modal-student-alias').textContent = alias;
  document.getElementById('modal-student-pseudonym').textContent = pseudonimo;

  const container = document.getElementById('modal-qr-container');
  container.innerHTML = '';

  if (window.QRCode) {
    new QRCode(container, {
      text: pseudonimo,
      width: 180,
      height: 180,
      colorDark: "#0f172a",
      colorLight: "#ffffff",
      correctLevel: QRCode.CorrectLevel.H
    });
  }

  const btnScan = document.getElementById('btn-scan-this-student');
  btnScan.onclick = () => {
    closeStudentQrModal();
    processScan(pseudonimo);
  };

  document.getElementById('student-qr-modal').classList.add('show');
}

function closeStudentQrModal() {
  document.getElementById('student-qr-modal').classList.remove('show');
}

// ==========================================================================
// CONEXIÓN MÓVIL (QR CON IP LOCAL PARA ANDROID / IOS)
// ==========================================================================
function openMobileConnectModal() {
  if (!state.serverInfo) return;

  const allIps = state.serverInfo.all_ips || [{ ip: state.serverInfo.local_ip, label: 'Wi-Fi', is_primary: true }];
  const selectContainer = document.getElementById('mobile-ip-selector-container');
  const ipSelect = document.getElementById('mobile-ip-select');

  if (allIps.length > 1) {
    selectContainer.style.display = 'block';
    ipSelect.innerHTML = '';
    allIps.forEach(item => {
      const opt = document.createElement('option');
      opt.value = item.ip;
      opt.textContent = `${item.ip} (${item.label})`;
      if (item.is_primary) opt.selected = true;
      ipSelect.appendChild(opt);
    });

    ipSelect.onchange = () => {
      renderMobileQr(ipSelect.value);
    };
  } else {
    selectContainer.style.display = 'none';
  }

  const selectedIp = (allIps.length > 0) ? allIps[0].ip : state.serverInfo.local_ip;
  renderMobileQr(selectedIp);
  document.getElementById('mobile-connect-modal').classList.add('show');
}

function renderMobileQr(ip) {
  const port = (state.serverInfo && state.serverInfo.port) ? state.serverInfo.port : 8000;
  const url = `http://${ip}:${port}`;
  document.getElementById('mobile-url-display').textContent = url;

  const container = document.getElementById('mobile-qr-container');
  container.innerHTML = '';

  if (window.QRCode) {
    new QRCode(container, {
      text: url,
      width: 190,
      height: 190,
      colorDark: "#0f172a",
      colorLight: "#ffffff",
      correctLevel: QRCode.CorrectLevel.M
    });
  }
}

function closeMobileConnectModal() {
  document.getElementById('mobile-connect-modal').classList.remove('show');
}

// ==========================================================================
// BASE DE DATOS Y CLASIFICACIÓN (RANKING & LOGS SQLITE)
// ==========================================================================
async function loadDatabaseData() {
  try {
    // 1. Cargar Ranking
    const resAlumnos = await fetch('/api/alumnos');
    const dataAlumnos = await resAlumnos.json();
    state.students = dataAlumnos.alumnos || [];

    const rankingContainer = document.getElementById('ranking-container');
    rankingContainer.innerHTML = '';

    state.students.forEach((alumno, idx) => {
      const pos = idx + 1;
      let posClass = '';
      let medal = pos;
      if (pos === 1) { posClass = 'pos-1'; medal = '🥇'; }
      else if (pos === 2) { posClass = 'pos-2'; medal = '🥈'; }
      else if (pos === 3) { posClass = 'pos-3'; medal = '🥉'; }

      const item = document.createElement('div');
      item.className = 'ranking-item';
      item.innerHTML = `
        <div class="rank-pos ${posClass}">${medal}</div>
        <div class="rank-info">
          <div class="rank-alias">${alumno.alias}</div>
          <div class="rank-pseudonym">${alumno.pseudonimo} • ${alumno.grupo || 'ESO'}</div>
        </div>
        <div class="rank-points">${alumno.total_puntos} pts</div>
      `;
      rankingContainer.appendChild(item);
    });

    // 2. Cargar Registros Históricos
    const resLogs = await fetch('/api/registros');
    const dataLogs = await resLogs.json();
    state.logs = dataLogs.registros || [];
    renderLogsTable(state.logs);

  } catch (err) {
    console.error('Error cargando datos de BBDD:', err);
  }
}

function renderLogsTable(logs) {
  const tbody = document.getElementById('logs-tbody');
  tbody.innerHTML = '';

  if (logs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 18px;">No hay registros de escaneos hoy en la base de datos.</td></tr>';
    return;
  }

  logs.forEach(log => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="font-family: monospace; color: var(--text-muted);">${log.hora}</td>
      <td><strong>${log.pseudonimo}</strong><br><span style="font-size: 0.72rem; color: var(--text-secondary);">${log.alias || ''}</span></td>
      <td><span style="text-transform: capitalize;">${log.seccion}</span></td>
      <td><strong style="color: #38bdf8;">+${log.puntos}</strong></td>
    `;
    tbody.appendChild(tr);
  });
}

// Filtro de registros
document.getElementById('filter-pseudonym').addEventListener('input', (e) => {
  const q = e.target.value.toLowerCase().trim();
  const filtered = state.logs.filter(l => 
    l.pseudonimo.toLowerCase().includes(q) || 
    (l.alias && l.alias.toLowerCase().includes(q)) ||
    l.seccion.toLowerCase().includes(q)
  );
  renderLogsTable(filtered);
});

// Exportar a CSV
function exportToCsv() {
  if (!state.logs || state.logs.length === 0) {
    alert('No hay registros para exportar.');
    return;
  }

  let csvContent = "data:text/csv;charset=utf-8,";
  csvContent += "ID,Pseudonimo,Alias,Seccion,Puntos,Fecha,Hora\n";

  state.logs.forEach(l => {
    csvContent += `"${l.id}","${l.pseudonimo}","${l.alias || ''}","${l.seccion}","${l.puntos}","${l.fecha}","${l.hora}"\n`;
  });

  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", `puntos_escolar_${new Date().toISOString().slice(0,10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// Resetear Base de Datos de Prueba
async function resetDatabase() {
  if (!confirm('¿Seguro que deseas reiniciar todos los registros y puntuaciones a 0 para una nueva demostración?')) {
    return;
  }

  try {
    const res = await fetch('/api/reset', { method: 'POST' });
    const data = await res.json();
    alert(data.message);
    loadDatabaseData();
    loadStudentsAndDemoChips();
  } catch (err) {
    alert('Error al reiniciar base de datos: ' + err.message);
  }
}

// ==========================================================================
// INICIALIZACIÓN Y VINCULACIÓN DE EVENTOS
// ==========================================================================
document.addEventListener('DOMContentLoaded', () => {
  // 1. Eventos del Teclado Numérico (PIN pad)
  document.querySelectorAll('.numpad .num-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const key = btn.getAttribute('data-key');
      handlePinInput(key);
    });
  });

  // Botón rellenar clave demo automáticamente
  document.getElementById('btn-quick-pin').addEventListener('click', () => {
    state.pinBuffer = '0000';
    updatePinDots();
    verifyPin('0000');
  });

  // 2. Eventos de las 4 Secciones
  document.querySelectorAll('.section-card').forEach(card => {
    card.addEventListener('click', () => {
      const seccion = card.getAttribute('data-seccion');
      selectSection(seccion);
    });
  });

  // Botón cambiar sección desde el escáner
  document.getElementById('btn-change-section').addEventListener('click', () => {
    switchView('view-sections');
  });

  // Manejador común para decodificar fotos y archivos QR
  async function processQrFile(file) {
    if (!file) return;
    if (!state.html5QrCode) await initQrScanner();

    try {
      feedback.playClick();
      const decodedResult = await state.html5QrCode.scanFile(file, true);
      processScan(decodedResult);
    } catch (err) {
      alert('No se detectó ningún código QR válido en la imagen. Intenta enfocar más de cerca o con mejor iluminación.');
    }
  }

  // 3. Controles de Cámara y Captura
  document.getElementById('btn-toggle-camera').addEventListener('click', () => {
    if (state.isCameraRunning) {
      stopCamera();
    } else {
      startCamera();
    }
  });

  document.getElementById('btn-flip-camera').addEventListener('click', flipCamera);

  const quickStartBtn = document.getElementById('btn-quick-start-cam');
  if (quickStartBtn) quickStartBtn.addEventListener('click', startCamera);

  const retryBtn = document.getElementById('btn-retry-camera');
  if (retryBtn) retryBtn.addEventListener('click', startCamera);

  // Selector de cámara si hay varios dispositivos detectados
  const camSelect = document.getElementById('camera-select');
  if (camSelect) {
    camSelect.addEventListener('change', async (e) => {
      state.selectedCameraId = e.target.value;
      if (state.isCameraRunning) {
        await stopCamera();
        await startCamera();
      }
    });
  }

  // Captura instantánea con la cámara nativa del móvil / PC
  const qrCameraInput = document.getElementById('qr-input-camera');
  if (qrCameraInput) {
    qrCameraInput.addEventListener('change', async (e) => {
      if (e.target.files.length === 0) return;
      await processQrFile(e.target.files[0]);
      e.target.value = '';
    });
  }

  const qrCameraFallbackInput = document.getElementById('qr-input-camera-fallback');
  if (qrCameraFallbackInput) {
    qrCameraFallbackInput.addEventListener('change', async (e) => {
      if (e.target.files.length === 0) return;
      await processQrFile(e.target.files[0]);
      e.target.value = '';
    });
  }

  // Subida de imagen QR desde galería / archivo
  document.getElementById('qr-input-file').addEventListener('change', async (e) => {
    if (e.target.files.length === 0) return;
    await processQrFile(e.target.files[0]);
    e.target.value = '';
  });

  // 4. Navegación Inferior (Mobile Bottom Nav)
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetView = btn.getAttribute('data-view');
      switchView(targetView);
    });
  });

  document.getElementById('btn-goto-bbdd').addEventListener('click', () => {
    switchView('view-database');
  });

  document.getElementById('btn-back-to-sections').addEventListener('click', () => {
    switchView('view-sections');
  });

  // 5. Pestañas de Base de Datos
  document.getElementById('tab-ranking').addEventListener('click', () => {
    document.getElementById('tab-ranking').classList.add('active');
    document.getElementById('tab-logs').classList.remove('active');
    document.getElementById('tab-content-ranking').style.display = 'block';
    document.getElementById('tab-content-logs').style.display = 'none';
  });

  document.getElementById('tab-logs').addEventListener('click', () => {
    document.getElementById('tab-logs').classList.add('active');
    document.getElementById('tab-ranking').classList.remove('active');
    document.getElementById('tab-content-ranking').style.display = 'none';
    document.getElementById('tab-content-logs').style.display = 'block';
  });

  document.getElementById('btn-refresh-db').addEventListener('click', loadDatabaseData);
  document.getElementById('btn-export-csv').addEventListener('click', exportToCsv);
  document.getElementById('btn-reset-db').addEventListener('click', resetDatabase);

  // 6. Modal de Feedback
  document.getElementById('btn-close-feedback').addEventListener('click', hideFeedbackModal);

  // 7. Modales QR
  document.getElementById('btn-close-qr-modal').addEventListener('click', closeStudentQrModal);
  document.getElementById('btn-open-all-cards').addEventListener('click', () => {
    if (state.students.length > 0) {
      openStudentQrModal(state.students[0].pseudonimo, state.students[0].alias);
    }
  });

  // 8. Modal Conexión Móvil
  document.getElementById('btn-mobile-connect').addEventListener('click', openMobileConnectModal);
  document.getElementById('btn-close-mobile-modal').addEventListener('click', closeMobileConnectModal);

  // 9. Cierre Web (Logout)
  document.getElementById('btn-logout').addEventListener('click', () => {
    if (confirm('¿Cerrar sesión de profesor y bloquear la página?')) {
      state.isAuthenticated = false;
      state.pinBuffer = '';
      updatePinDots();
      stopCamera();
      evaluateAppFlow();
    }
  });

  // 10. Switch Simulación Horario Lectivo
  const simToggle = document.getElementById('sim-hours-toggle');
  simToggle.addEventListener('change', (e) => {
    state.simulatedSchoolHours = e.target.checked;
    checkScheduleStatus();
  });

  document.getElementById('btn-force-open-demo').addEventListener('click', () => {
    state.simulatedSchoolHours = true;
    simToggle.checked = true;
    checkScheduleStatus();
  });

  // 11. Alternar Tema Claro / Oscuro
  document.getElementById('btn-theme-toggle').addEventListener('click', () => {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    html.setAttribute('data-theme', newTheme);
    document.getElementById('btn-theme-toggle').textContent = newTheme === 'light' ? '☀️' : '🌙';
  });

  // Iniciar sondeo de hora y carga inicial
  checkScheduleStatus();
  setInterval(checkScheduleStatus, 15000); // Comprueba hora periódicamente
  loadStudentsAndDemoChips();
});
