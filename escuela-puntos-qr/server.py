#!/usr/bin/env python3 
# -*- coding: utf-8 -*-
"""
Servidor HTTP y API REST para CONTACLETA - Recuento de participación RIDE
Utiliza exclusivamente la librería estándar de Python (http.server + sqlite3).
Compatible con ejecución local, Render.com y acceso en red Wi-Fi desde Android e iOS.
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
import re
from urllib.parse import urlparse, parse_qs

def get_ssl_context():
    """Carga certificado auto-firmado si está presente."""
    cert_path = os.path.join(os.path.dirname(__file__), "cert.pem")
    key_path = os.path.join(os.path.dirname(__file__), "key.pem")
    if os.path.isfile(cert_path) and os.path.isfile(key_path):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
        return ctx
    return None

PORT = int(os.environ.get("PORT", 8000))
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "escuela_puntos.db")
STATIC_DIR = os.path.dirname(os.path.abspath(__file__))

SECCIONES_CONFIG = {
    "llegada": {"nombre": "🚲 Al cole en bici", "puntos": 1, "color": "#0284c7"},
    "taller": {"nombre": "🛠️ Taller", "puntos": 0, "color": "#ea580c"},
    "excursiones": {"nombre": "🛣️ Ruta en bici", "puntos": 0, "color": "#16a34a"},
    "divulgacion": {"nombre": "📢 Divulgación", "puntos": 0, "color": "#9333ea"}
}

PIN_DOCENTE = "0000"

# Lista completa de los 50 alumnos extraídos de los carnets QR
ALUMNOS_INICIALES = [
    ("https://www.berthemorisot.com", "Berthe Morisot", "Grupo A"),
    ("https://www.leonardodavinci.com", "Leonardo Da Vinci", "Grupo A"),
    ("https://www.ride-andywarhol.com", "Andy Warhol", "Grupo A"),
    ("https://www.ride-artemisiagentileschi.com", "Artemisia Gentileschi", "Grupo A"),
    ("https://www.ride-boticellli.com", "Botticelli", "Grupo A"),
    ("https://www.ride-caravaggio.com", "Caravaggio", "Grupo A"),
    ("https://www.ride-cezanne.com", "Cézanne", "Grupo A"),
    ("https://www.ride-clarapeeters.com", "Clara Peeters", "Grupo A"),
    ("https://www.ride-dalí.com", "Dalí", "Grupo A"),
    ("https://www.ride-elbosco.com", "El Bosco", "Grupo A"),
    ("https://www.ride-elisabethvigéelebrun.com", "Elisabeth Vigée Le Brun", "Grupo A"),
    ("https://www.ride-georgiaokeeffe.com", "Georgia O'Keeffe", "Grupo A"),
    ("https://www.ride-goya.com", "Goya", "Grupo A"),
    ("https://www.ride-gustavklimt.com", "Gustav Klimt", "Grupo A"),
    ("https://www.ride-helenfrankenthaler.com", "Helen Frankenthaler", "Grupo A"),
    ("https://www.ride-henrimatisse.com", "Henri Matisse", "Grupo A"),
    ("https://www.ride-hilmaafklint.com", "Hilma af Klint", "Grupo A"),
    ("https://www.ride-judithleyster.com", "Judith Leyster", "Grupo A"),
    ("https://www.ride-laviniafontana.com", "Lavinia Fontana", "Grupo A"),
    ("https://www.ride-leonoracarrington.com", "Leonora Carrington", "Grupo A"),
    ("https://www.ride-louisebourgeois.com", "Louise Bourgeois", "Grupo A"),
    ("https://www.ride-manet.com", "Manet", "Grupo A"),
    ("https://www.ride-mariablanchard.com", "María Blanchard", "Grupo A"),
    ("https://www.ride-miguelangel.com", "Miguel Ángel", "Grupo A"),
    ("https://www.ride-miro.com", "Miró", "Grupo A"),
    ("https://www.ride-monet.com", "Monet", "Grupo A"),
    ("https://www.ride-munch.com", "Munch", "Grupo A"),
    ("https://www.ride-paulgauguin.com", "Paul Gauguin", "Grupo A"),
    ("https://www.ride-picasso.com", "Picasso", "Grupo A"),
    ("https://www.ride-pollock.com", "Pollock", "Grupo A"),
    ("https://www.ride-rachelruysch.com", "Rachel Ruysch", "Grupo A"),
    ("https://www.ride-raphael.com", "Raphael", "Grupo A"),
    ("https://www.ride-rembrandt.com", "Rembrandt", "Grupo A"),
    ("https://www.ride-remediosvaro.com", "Remedios Varo", "Grupo A"),
    ("https://www.ride-renoir.com", "Renoir", "Grupo A"),
    ("https://www.ride-rosabonheur.com", "Rosa Bonheur", "Grupo A"),
    ("https://www.ride-sofonisbaanguissola.com", "Sofonisba Anguissola", "Grupo A"),
    ("https://www.ride-soniadelaunay.com", "Sonia Delaunay", "Grupo A"),
    ("https://www.ride-susanvaladon.com", "Suzanne Valadon", "Grupo A"),
    ("https://www.ride-tamaradelempika.com", "Tamara de Lempicka", "Grupo A"),
    ("https://www.ride-tiziano.com", "Tiziano", "Grupo A"),
    ("https://www.ride-vanderweyden.com", "Van der Weyden", "Grupo A"),
    ("https://www.ride-vangogh.com", "Van Gogh", "Grupo A"),
    ("https://www.ride-velázquez.com", "Velázquez", "Grupo A"),
    ("https://www.ride-yayoirokusama.com", "Yayoi Kusama", "Grupo A"),
    ("https://www.ride-fridakahlo.com", "Frida Kahlo", "1º ESO A"),
    ("https://www.ride-marujamallo.com", "Maruja Mallo", "1º ESO A"),
    ("https://www.ride-marycassatt.com", "Mary Cassatt", "4º ESO C"),
    ("https://www.ride-paulamodersohnbecker.com", "Paula Modersohn-Becker", "1º CFGS")
]

# Diccionario inteligente para mapeo inmediato de URLs a nombres limpios y grupos
MAPA_NOMBRES_CONOCIDOS = {url.lower(): (nombre, grupo) for url, nombre, grupo in ALUMNOS_INICIALES}

def extraer_nombre_desde_qr(pseudonimo):
    """Extrae un nombre legible si el QR es una URL o código sin alias explícito."""
    clave_lower = pseudonimo.lower().strip()
    if clave_lower in MAPA_NOMBRES_CONOCIDOS:
        return MAPA_NOMBRES_CONOCIDOS[clave_lower][0]
    
    # Si es una URL del tipo https://www.ride-nombreapellido.com
    match = re.search(r'ride-([a-zA-Z0-9\-]+)', clave_lower)
    if match:
        limpio = match.group(1).replace('-', ' ').title()
        return limpio
    return f"Alumno ({pseudonimo})"

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
    
    if not candidates:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            candidates.append(s.getsockname()[0])
            s.close()
        except Exception:
            candidates.append("127.0.0.1")

    def ip_score(ip):
        if ip.startswith("192.168."):
            return 100
        elif ip.startswith("172."):
            return 50
        elif ip.startswith("10."):
            return 10
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

def sincronizar_alumnos_base(cursor):
    """Elimina los alumnos demo antiguos y asegura que los alumnos del código tengan su nombre."""
    # Eliminar antiguos alumnos demo (ALUM-LINCE-01, ALUM-HALCON-02, etc.)
    cursor.execute("DELETE FROM alumnos WHERE pseudonimo LIKE 'ALUM-%'")
    
    for pseudonimo, alias, grupo in ALUMNOS_INICIALES:
        # Buscar si ya existe (ignorando mayúsculas/minúsculas)
        cursor.execute("SELECT id FROM alumnos WHERE LOWER(pseudonimo) = LOWER(?)", (pseudonimo,))
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE alumnos SET pseudonimo = ?, alias = ?, grupo = ? WHERE id = ?",
                (pseudonimo, alias, grupo, row[0])
            )
        else:
            cursor.execute(
                "INSERT INTO alumnos (pseudonimo, alias, grupo, total_puntos) VALUES (?, ?, ?, 0)",
                (pseudonimo, alias, grupo)
            )

def init_database():
    """Inicializa las tablas SQLite y sincroniza los alumnos configurados en el código."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Tabla de alumnos
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

    sincronizar_alumnos_base(cursor)
    conn.commit()
    conn.close()

def es_horario_lectivo(dt=None):
    """
    Comprueba si el momento corresponde al horario escolar:
    De Lunes (0) a Viernes (4), entre las 08:00 y las 14:30.
    """
    if dt is None:
        dt = datetime.datetime.now()
    
    es_dia_lectivo = 0 <= dt.weekday() <= 4
    hora_actual = dt.time()
    hora_inicio = datetime.time(8, 0, 0)
    hora_fin = datetime.time(14, 30, 0)
    
    return es_dia_lectivo and (hora_inicio <= hora_actual <= hora_fin)

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
            cursor.execute("SELECT id, pseudonimo, alias, grupo, total_puntos FROM alumnos ORDER BY total_puntos DESC, alias ASC")
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
                    "docente": "Profesor RIDE",
                    "rol": "docente"
                })
            else:
                self._send_json({
                    "ok": False,
                    "message": "Clave incorrecta. Inténtelo de nuevo."
                }, status=401)
            return

        elif path == "/api/escanear":
            raw_input = str(body.get("pseudonimo", "")).strip()
            seccion = str(body.get("seccion", "")).strip().lower()
            simulated = bool(body.get("simulated", False))
            
            if not raw_input:
                self._send_json({"ok": False, "message": "Código QR / Pseudónimo no proporcionado."}, status=400)
                return

            if seccion not in SECCIONES_CONFIG:
                self._send_json({"ok": False, "message": f"Sección inválida: {seccion}"}, status=400)
                return

            # Si el contenido del QR incluye datos separados por coma ("URL, Nombre, Grupo")
            parts = [p.strip() for p in raw_input.split(",")]
            pseudonimo_raw = parts[0]
            extracted_alias = parts[1] if len(parts) > 1 and parts[1] else None
            extracted_grupo = parts[2] if len(parts) > 2 and parts[2] else None

            now = datetime.datetime.now()
            fecha_hoy = now.strftime("%Y-%m-%d")
            hora_actual = now.strftime("%H:%M:%S")

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
                # 1. Buscar alumno existente por pseudónimo (insensible a mayúsculas/minúsculas)
                cursor.execute("SELECT id, pseudonimo, alias, grupo, total_puntos FROM alumnos WHERE LOWER(pseudonimo) = LOWER(?)", (pseudonimo_raw,))
                alumno = cursor.fetchone()

                if not alumno:
                    # Determinar nombre y grupo si se escanea un QR nuevo
                    clave_lower = pseudonimo_raw.lower()
                    if not extracted_alias:
                        extracted_alias = extraer_nombre_desde_qr(pseudonimo_raw)
                    if not extracted_grupo:
                        extracted_grupo = MAPA_NOMBRES_CONOCIDOS.get(clave_lower, (None, "Grupo RIDE"))[1]

                    cursor.execute(
                        "INSERT INTO alumnos (pseudonimo, alias, grupo, total_puntos) VALUES (?, ?, ?, 0)",
                        (pseudonimo_raw, extracted_alias, extracted_grupo)
                    )
                    conn.commit()
                    cursor.execute("SELECT id, pseudonimo, alias, grupo, total_puntos FROM alumnos WHERE LOWER(pseudonimo) = LOWER(?)", (pseudonimo_raw,))
                    alumno = cursor.fetchone()
                else:
                    # Si el QR traía nombre explícito y en la BD tenía un nombre genérico, actualizarlo
                    if extracted_alias and (not alumno["alias"] or alumno["alias"].startswith("Estudiante ")):
                        cursor.execute("UPDATE alumnos SET alias = ? WHERE id = ?", (extracted_alias, alumno["id"]))
                        conn.commit()
                        cursor.execute("SELECT id, pseudonimo, alias, grupo, total_puntos FROM alumnos WHERE id = ?", (alumno["id"],))
                        alumno = cursor.fetchone()

                alumno_id = alumno["id"]
                pseudonimo_db = alumno["pseudonimo"]
                alumno_alias = alumno["alias"] or extraer_nombre_desde_qr(pseudonimo_db)
                puntos_anteriores = alumno["total_puntos"]

                # 2. Verificar duplicado en el mismo día y sección
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
                        "message": f"{alumno_alias} ya ha sido registrado/a hoy en '{nombre_seccion}' a las {hora_previa}. (Solo 1 escaneo por sección al día).",
                        "alumno": {"pseudonimo": pseudonimo_db, "alias": alumno_alias},
                        "seccion": nombre_seccion,
                        "hora_previa": hora_previa
                    }, status=409)
                    return

                # 3. Registrar el escaneo y sumar puntos
                cursor.execute(
                    "INSERT INTO registros (alumno_id, pseudonimo, seccion, puntos, fecha, hora) VALUES (?, ?, ?, ?, ?, ?)",
                    (alumno_id, pseudonimo_db, seccion, puntos_seccion, fecha_hoy, hora_actual)
                )

                nuevo_total = puntos_anteriores + puntos_seccion
                cursor.execute("UPDATE alumnos SET total_puntos = ? WHERE id = ?", (nuevo_total, alumno_id))
                conn.commit()
                conn.close()

                self._send_json({
                    "ok": True,
                    "message": f"¡Participación registrada! +{puntos_seccion} pts en {nombre_seccion}",
                    "alumno": {
                        "id": alumno_id,
                        "pseudonimo": pseudonimo_db,
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

            except sqlite3.IntegrityError:
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
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM registros")
            cursor.execute("UPDATE alumnos SET total_puntos = 0")
            sincronizar_alumnos_base(cursor)
            conn.commit()
            conn.close()
            self._send_json({"ok": True, "message": "Base de datos sincronizada y puntuaciones reiniciadas a 0 correctamente."})
            return

        self._send_json({"ok": False, "message": "Ruta no encontrada"}, status=404)

def run():
    init_database()
    best_ip = get_best_local_ip()
    
    server_address = ("0.0.0.0", PORT)
    httpd = http.server.ThreadingHTTPServer(server_address, EscuelaPointsHandler)
    httpd.allow_reuse_address = True

    ssl_ctx = get_ssl_context()
    protocol = "https" if ssl_ctx else "http"
    if ssl_ctx:
        httpd.socket = ssl_ctx.wrap_socket(httpd.socket, server_side=True)

    print("=" * 65)
    print("  CONTACLETA - SISTEMA ESCOLAR DE PUNTOS POR QR ACTIVO")
    print("=" * 65)
    print(f"  Acceso Local (PC):          {protocol}://localhost:{PORT}")
    print(f"  Acceso Móvil Wi-Fi:         {protocol}://{best_ip}:{PORT} (RECOMENDADO)")
    print("  Base de Datos SQLite:       escuela_puntos.db")
    print("  Clave PIN Profesor:         0000")
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
