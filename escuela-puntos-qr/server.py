#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servidor HTTP y API REST para Sistema de Puntos Escolar con Códigos QR
Utiliza exclusivamente la librería estándar de Python (http.server + sqlite3).
Compatible con ejecución local y acceso en red Wi-Fi desde Android e iOS.
"""

import http.server
import socketserver
import sqlite3
import json
import os
import sys
import ssl
import socket
import datetime
from urllib.parse import urlparse, parse_qs

def get_ssl_context():
    """Load self‑signed certificate if present.
    Returns an ssl.SSLContext or None.
    """
    cert_path = os.path.join(os.path.dirname(__file__), "cert.pem")
    key_path = os.path.join(os.path.dirname(__file__), "key.pem")
    if os.path.isfile(cert_path) and os.path.isfile(key_path):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
        return ctx
    return None

PORT = 8000
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "escuela_puntos.db")
STATIC_DIR = os.path.dirname(os.path.abspath(__file__))

SECCIONES_CONFIG = {
    "llegada": {"nombre": "🚲 Al cole en bici", "puntos": 1, "color": "#0284c7"},
    "taller": {"nombre": "🛠️ Taller", "puntos": 0, "color": "#ea580c"},
    "excursiones": {"nombre": "🛣️ Ruta en bici", "puntos": 0, "color": "#16a34a"},
    "divulgacion": {"nombre": "📢 Divulgación", "puntos": 0, "color": "#9333ea"}
}

PIN_DOCENTE = "0000"

def get_all_local_ips():
    """Detecta y prioriza todas las interfaces de red locales (Wi-Fi vs VPN)."""
    candidates = []
    try:
        _, _, ips = socket.gethostbyname_ex(socket.gethostname())
        for ip in ips:
            if not ip.startswith("127."):
                candidates.append(ip)
    except Exception:
        pass
    
    # Fallback si estuviera vacío
    if not candidates:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            candidates.append(s.getsockname()[0])
            s.close()
        except Exception:
            candidates.append("127.0.0.1")

    # Priorización: Las redes domésticas/escolares Wi-Fi estándar son 192.168.x.x
    def ip_score(ip):
        if ip.startswith("192.168."):
            return 100  # Máxima prioridad: Wi-Fi estándar
        elif ip.startswith("172."):
            return 50   # Prioridad media: Redes privadas clase B
        elif ip.startswith("10."):
            return 10   # Baja prioridad: VPNs como McAfee VPN o WSL
        return 0

    candidates.sort(key=ip_score, reverse=True)
    
    result = []
    for idx, ip in enumerate(candidates):
        label = "Wi-Fi / Red Local (Recomendado)" if ip.startswith("192.168.") else ("VPN / Virtual" if ip.startswith("10.") else "Red Privada")
        result.append({
            "ip": ip,
            "label": label,
            "is_primary": (idx == 0)
        })
    return result

def get_best_local_ip():
    """Retorna la mejor IP (Wi-Fi) detectada."""
    all_ips = get_all_local_ips()
    return all_ips[0]["ip"] if all_ips else "127.0.0.1"

def init_database():
    """Inicializa las tablas SQLite y precarga alumnos con pseudónimos de prueba."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Tabla de alumnos (protección de datos: usamos pseudónimos como identificador público)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alumnos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pseudonimo TEXT UNIQUE NOT NULL,
        alias TEXT,
        grupo TEXT DEFAULT 'Grupo A',
        total_puntos INTEGER DEFAULT 0,
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Tabla de registros de puntos y escaneos
    # Regla: Los QR solo se pueden escanear una vez por sección de 08:00 a 14:30 de L-V
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS registros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alumno_id INTEGER NOT NULL,
        pseudonimo TEXT NOT NULL,
        seccion TEXT NOT NULL,
        puntos INTEGER NOT NULL,
        fecha TEXT NOT NULL,
        hora TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (alumno_id) REFERENCES alumnos (id),
        UNIQUE(alumno_id, seccion, fecha)
    );
    """)

    # Precarga de alumnos de muestra si está vacía
    cursor.execute("SELECT COUNT(*) FROM alumnos")
    count = cursor.fetchone()[0]
    if count == 0:
        alumnos_demo = [
            ("ALUM-LINCE-01", "Lince Ágil", "1º ESO A"),
            ("https://www.ride-laviniafontana.com, Lavinia Fontana, 1ºESO A")
        ]
        cursor.executemany(
            "INSERT INTO alumnos (pseudonimo, alias, grupo, total_puntos) VALUES (?, ?, ?, 0)",
            alumnos_demo
        )
        conn.commit()
    conn.close()

def es_horario_lectivo(dt=None):
    """
    Comprueba si el momento corresponde al horario escolar:
    De Lunes (0) a Viernes (4), entre las 08:00 y las 14:30.
    """
    if dt is None:
        dt = datetime.datetime.now()
    
    # 0 = Lunes, 4 = Viernes, 5 = Sábado, 6 = Domingo
    es_dia_lectivo = 0 <= dt.weekday() <= 4
    
    hora_actual = dt.time()
    hora_inicio = datetime.time(8, 0, 0)
    hora_fin = datetime.time(14, 30, 0)
    
    dentro_horario = hora_inicio <= hora_actual <= hora_fin
    return es_dia_lectivo and dentro_horario

class EscuelaPointsHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_OPTIONS(self):
        """Soporte CORS para pruebas en red."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Simulated-School-Hours")
        self.end_headers()

    def _send_json(self, data, status=200):
        response_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Connection", "close")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def _read_json(self):
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len == 0:
                return {}
            post_data = self.rfile.read(content_len)
            return json.loads(post_data.decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            now = datetime.datetime.now()
            lectivo_real = es_horario_lectivo(now)
            dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            all_ips = get_all_local_ips()
            best_ip = get_best_local_ip()
            self._send_json({
                "ok": True,
                "current_time": now.strftime("%H:%M:%S"),
                "current_date": now.strftime("%Y-%m-%d"),
                "day_name": dias_semana[now.weekday()],
                "is_school_hours": lectivo_real,
                "schedule_rule": "Lunes a Viernes de 08:00 a 14:30",
                "local_ip": best_ip,
                "all_ips": all_ips,
                "port": PORT
            })
            return

        elif path == "/api/alumnos":
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, pseudonimo, alias, grupo, total_puntos FROM alumnos ORDER BY total_puntos DESC, pseudonimo ASC")
            rows = cursor.fetchall()
            alumnos = [dict(row) for row in rows]
            conn.close()
            self._send_json({"ok": True, "alumnos": alumnos})
            return

        elif path == "/api/registros":
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
            SELECT r.id, r.alumno_id, r.pseudonimo, a.alias, r.seccion, r.puntos, r.fecha, r.hora, r.timestamp
            FROM registros r
            LEFT JOIN alumnos a ON r.alumno_id = a.id
            ORDER BY r.id DESC
            LIMIT 100
            """)
            rows = cursor.fetchall()
            registros = [dict(row) for row in rows]
            conn.close()
            self._send_json({"ok": True, "registros": registros})
            return

        # Servir estáticos normales
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_json()

        if path == "/api/login":
            pin = str(body.get("pin", "")).strip()
            if pin == PIN_DOCENTE:
                self._send_json({
                    "ok": True,
                    "message": "Autenticación correcta",
                    "docente": "Profesor Demo",
                    "rol": "docente"
                })
            else:
                self._send_json({
                    "ok": False,
                    "message": "Clave incorrecta. Inténtelo de nuevo."
                }, status=401)
            return

        elif path == "/api/escanear":
            pseudonimo = str(body.get("pseudonimo", "")).strip().upper()
            seccion = str(body.get("seccion", "")).strip().lower()
            simulated = bool(body.get("simulated", False))
            
            if not pseudonimo:
                self._send_json({"ok": False, "message": "Código QR / Pseudónimo no proporcionado."}, status=400)
                return

            if seccion not in SECCIONES_CONFIG:
                self._send_json({"ok": False, "message": f"Sección inválida: {seccion}"}, status=400)
                return

            now = datetime.datetime.now()
            fecha_hoy = now.strftime("%Y-%m-%d")
            hora_actual = now.strftime("%H:%M:%S")

            # Validación de horario lectivo (Lunes a Viernes 08:00 a 14:30)
            if not simulated and not es_horario_lectivo(now):
                self._send_json({
                    "ok": False,
                    "error_code": "OUT_OF_SCHEDULE",
                    "message": "El escaneo solo está permitido en horario lectivo (Lunes a Viernes de 08:00 a 14:30). Utilice el 'Modo Simulación' si desea realizar pruebas fuera de este horario."
                }, status=403)
                return

            puntos_seccion = SECCIONES_CONFIG[seccion]["puntos"]
            nombre_seccion = SECCIONES_CONFIG[seccion]["nombre"]

            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            try:
                # 1. Buscar alumno o crear si es nuevo pseudónimo
                cursor.execute("SELECT id, pseudonimo, alias, total_puntos FROM alumnos WHERE pseudonimo = ?", (pseudonimo,))
                alumno = cursor.fetchone()
                if not alumno:
                    # Crear nuevo alumno con este pseudónimo
                    alias_gen = f"Estudiante {pseudonimo}"
                    cursor.execute("INSERT INTO alumnos (pseudonimo, alias, total_puntos) VALUES (?, ?, 0)", (pseudonimo, alias_gen))
                    conn.commit()
                    cursor.execute("SELECT id, pseudonimo, alias, total_puntos FROM alumnos WHERE pseudonimo = ?", (pseudonimo,))
                    alumno = cursor.fetchone()

                alumno_id = alumno["id"]
                alumno_alias = alumno["alias"]
                puntos_anteriores = alumno["total_puntos"]

                # 2. Verificar si YA ha sido escaneado hoy en esta sección
                cursor.execute(
                    "SELECT hora FROM registros WHERE alumno_id = ? AND seccion = ? AND fecha = ?",
                    (alumno_id, seccion, fecha_hoy)
                )
                previo = cursor.fetchone()

                if previo:
                    hora_previa = previo["hora"]
                    conn.close()
                    self._send_json({
                        "ok": False,
                        "error_code": "ALREADY_SCANNED",
                        "message": f"El alumno {pseudonimo} ya ha sido registrado hoy en '{nombre_seccion}' a las {hora_previa}. (Solo 1 escaneo por sección al día).",
                        "alumno": {"pseudonimo": pseudonimo, "alias": alumno_alias},
                        "seccion": nombre_seccion,
                        "hora_previa": hora_previa
                    }, status=409)
                    return

                # 3. Registrar el escaneo y otorgar puntos
                cursor.execute(
                    "INSERT INTO registros (alumno_id, pseudonimo, seccion, puntos, fecha, hora) VALUES (?, ?, ?, ?, ?, ?)",
                    (alumno_id, pseudonimo, seccion, puntos_seccion, fecha_hoy, hora_actual)
                )

                nuevo_total = puntos_anteriores + puntos_seccion
                cursor.execute("UPDATE alumnos SET total_puntos = ? WHERE id = ?", (nuevo_total, alumno_id))
                conn.commit()
                conn.close()

                self._send_json({
                    "ok": True,
                    "message": f"¡Puntos asignados con éxito! +{puntos_seccion} pts en {nombre_seccion}",
                    "alumno": {
                        "id": alumno_id,
                        "pseudonimo": pseudonimo,
                        "alias": alumno_alias,
                        "puntos_ganados": puntos_seccion,
                        "total_puntos": nuevo_total
                    },
                    "seccion": nombre_seccion,
                    "seccion_key": seccion,
                    "fecha": fecha_hoy,
                    "hora": hora_actual
                })
                return

            except sqlite3.IntegrityError as e:
                conn.close()
                self._send_json({
                    "ok": False,
                    "error_code": "ALREADY_SCANNED",
                    "message": f"Registro duplicado detectado para hoy en {nombre_seccion}."
                }, status=409)
                return
            except Exception as ex:
                conn.close()
                self._send_json({"ok": False, "message": f"Error interno: {str(ex)}"}, status=500)
                return

        elif path == "/api/reset":
            # Reseteo de demo para pruebas limpias
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM registros")
            cursor.execute("UPDATE alumnos SET total_puntos = 0")
            conn.commit()
            conn.close()
            self._send_json({"ok": True, "message": "Datos de registros y puntuaciones reiniciados correctamente."})
            return

        self._send_json({"ok": False, "message": "Ruta no encontrada"}, status=404)

def run():
    init_database()
    best_ip = get_best_local_ip()
    all_ips = get_all_local_ips()
    
    server_address = ("0.0.0.0", PORT)
    httpd = http.server.ThreadingHTTPServer(server_address, EscuelaPointsHandler)
    httpd.allow_reuse_address = True

    print("=" * 65)
    print("  SISTEMA ESCOLAR DE PUNTOS POR QR - SERVIDOR ACTIVO")
    print("=" * 65)
    print(f"  Acceso Local (PC):          http://localhost:{PORT}")
    print(f"  Acceso Móvil Wi-Fi:         http://{best_ip}:{PORT} (RECOMENDADO)")
    if len(all_ips) > 1:
        print("  Otras interfaces detectadas:")
        for item in all_ips:
            if item["ip"] != best_ip:
                print(f"    - http://{item['ip']}:{PORT} ({item['label']})")
    print("  Base de Datos SQLite:       escuela_puntos.db")
    print("  Clave PIN Profesor (Demo):  0000")
    print("  Horario Lectivo:            Lunes a Viernes 08:00 a 14:30")
    print("=" * 65)
    print("Presiona Ctrl+C para detener el servidor.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nDeteniendo servidor...")
        httpd.server_close()

if __name__ == "__main__":
    run()
