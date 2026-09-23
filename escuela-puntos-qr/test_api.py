import urllib.request
import urllib.error
import json

base = 'http://localhost:8000'

print('--- 1. Testing /api/status ---')
with urllib.request.urlopen(base + '/api/status') as r:
    status_data = json.loads(r.read())
    print('Status response:', status_data)

print('\n--- 2. Testing /api/login with invalid PIN (9999) ---')
req = urllib.request.Request(base + '/api/login', data=json.dumps({'pin': '9999'}).encode(), headers={'Content-Type': 'application/json'})
try:
    urllib.request.urlopen(req)
    print('ERROR: Should have failed')
except urllib.error.HTTPError as e:
    print(f'Correctly rejected (Status {e.code}): {e.read().decode()}')

print('\n--- 3. Testing /api/login with valid PIN (0000) ---')
req = urllib.request.Request(base + '/api/login', data=json.dumps({'pin': '0000'}).encode(), headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req) as r:
    print('Login OK:', r.read().decode())

print('\n--- 4. Testing /api/escanear (ALUM-LINCE-01 in llegada, +1 pt) ---')
payload = {'pseudonimo': 'ALUM-LINCE-01', 'seccion': 'llegada', 'simulated': True}
req = urllib.request.Request(base + '/api/escanear', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req) as r:
    res1 = json.loads(r.read())
    print('Scan result 1:', res1)

print('\n--- 5. Testing DUPLICATE scan in same section on same day ---')
req = urllib.request.Request(base + '/api/escanear', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
try:
    urllib.request.urlopen(req)
    print('ERROR: Duplicate was not rejected!')
except urllib.error.HTTPError as e:
    print(f'Duplicate correctly rejected (Status {e.code}): {e.read().decode()}')

print('\n--- 6. Testing scan in DIFFERENT section (ALUM-LINCE-01 in taller, +3 pts) ---')
payload2 = {'pseudonimo': 'ALUM-LINCE-01', 'seccion': 'taller', 'simulated': True}
req = urllib.request.Request(base + '/api/escanear', data=json.dumps(payload2).encode(), headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req) as r:
    res2 = json.loads(r.read())
    print('Scan result 2:', res2)

print('\n--- 7. Testing /api/registros ---')
with urllib.request.urlopen(base + '/api/registros') as r:
    logs = json.loads(r.read())
    print(f'Total registros in DB: {len(logs.get("registros", []))}')
    for log in logs.get("registros", []):
        print(f"  - [{log['hora']}] {log['pseudonimo']} -> {log['seccion']} (+{log['puntos']} pts)")

print('\n--- 8. Testing /api/alumnos ---')
with urllib.request.urlopen(base + '/api/alumnos') as r:
    alumnos = json.loads(r.read())
    for a in alumnos.get("alumnos", [])[:3]:
        print(f"  - {a['alias']} ({a['pseudonimo']}): {a['total_puntos']} pts")
