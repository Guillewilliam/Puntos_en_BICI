# 🚲 CONTACLETA - Recuento de Participación RIDE

<p align="center">
  <img src="imgLogo.jpeg" alt="Logo Contacleta" width="120" style="border-radius: 10px;">
</p>

Sistema web dinámico y liviano diseñado para el registro y recuento de participación del alumnado en actividades escolares mediante la lectura de **códigos QR** y pseudónimos protegidos. Cuenta con validación estricta de horario lectivo, persistencia de datos en **SQLite** y soporte completo multidispositivo (*Mobile-First* para Android e iOS).

---

## 🚀 Características Principales

- **📱 Diseño Mobile-First & Glassmorphism:** Interfaz optimizada para teléfonos móviles y tablets, con soporte para modo diurno y nocturno.
- **📷 Escáner QR Integrado:** Compatible con la librería `Html5Qrcode` para lectura en directo mediante la cámara, selección de lentes (frontal/trasera) o subida/captura instantánea de fotos de carnets QR.
- **🔒 Acceso Docente Seguro:** Panel protegido mediante un teclado numérico táctil (PIN Pad) con clave configurable (Demo: `0000`).
- **⏰ Control Horario Inteligente:** Validación automática de participación limitada al horario lectivo (Lunes a Viernes de 08:00 a 14:30), provisto de un *Modo Simulación* para pruebas en cualquier momento[cite: 1, 3].
- **📊 Base de Datos SQLite & Ranking:** Control de puntos acumulados, prevención de duplicados diarios por sección y visualización de un ranking escolar en tiempo real junto con el historial de registros[cite: 1, 3].
- **📥 Exportación y Conectividad Wi-Fi:** Herramienta integrada para exportar los registros a formato CSV y generador de QR de IP local para conectar rápidamente smartphones de la misma red Wi-Fi.

---

## 🛠️ Secciones y Puntuaciones

El sistema gestiona de forma diferenciada cuatro ámbitos de participación escolar:
1. **🚲 Al cole en bici:** Recuento de puntualidad e ingreso al centro escolar (`+1 pto`)[cite: 1, 3].
2. **🛠️ Taller:** Prácticas experimentales y proyectos (`+0 ptos`)[cite: 1, 3].
3. **🛣️ Ruta en bici:** Salidas culturales, visitas y naturaleza (`+0 ptos`)[cite: 1, 3].
4. **📢 Divulgación:** Presentaciones, debates y conferencias (`+0 ptos`)[cite: 1, 3].

---

## ⚙️ Tecnologías Utilizadas

- **Backend:** Python 3 (`http.server`, `sqlite3`, sockets para detección de red local y soporte opcional TLS/SSL)[cite: 3].
- **Frontend:** HTML5, CSS3 (Variables, Glassmorphism, diseño responsivo) y JavaScript vainilla (ES6+).
- **Librerías Externas (Locales):** 
  - `html5-qrcode.min.js` (para el motor de escaneo de códigos de barras y QR)[cite: 1, 8].
  - `qrcode.min.js` (para la generación dinámica de tarjetas de carnet QR)[cite: 1, 9].
- **Despliegue / Entorno:** Preparado para ejecución local en PC/Python y despliegues en la nube (como Render.com).

---

## 📂 Estructura del Proyecto

```text
├── index.html            # Interfaz principal de la aplicación (SPA basada en vistas)
├── server.py             # Servidor HTTP/API REST en Python y gestor de SQLite
├── run.bat               # Script de inicio rápido para entornos Windows
├── escuela_puntos.db     # Base de datos SQLite (generada automáticamente)
├── imgLogo.jpeg          # Logotipo oficial de CONTACLETA
├── css/
│   └── styles.css        # Estilos visuales adaptativos (Modo claro/oscuro)
└── js/
    ├── app.js            # Lógica cliente, gestión de vistas, síntesis de audio y cámara
    ├── qrcode.min.js     # Librería de generación de códigos QR
    └── html5-qrcode.min.js # Librería de escaneo de video y ficheros
