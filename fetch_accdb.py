#!/usr/bin/env python3
"""Descarga el .accdb mas reciente desde Zoho IMAP.

Variables de entorno:
  ZOHO_EMAIL          - tu direccion de mail en Zoho
  ZOHO_PASSWORD       - tu password de Zoho (o app password)
  EXPECTED_SENDER     - email del remitente del .accdb
  ZOHO_IMAP_HOST      - default: imap.zoho.com (cambiar a imap.zoho.eu, etc.)
  IMAP_FOLDER         - opcional. Si se setea, fuerza esa carpeta exacta.
                         Si no, busca en INBOX y en carpetas compartidas/Cotizador.
"""
import os, sys, email, imaplib, functools, re
from email.policy import default

print = functools.partial(print, flush=True)

EMAIL = os.environ.get('ZOHO_EMAIL', '').strip()
PASSWORD = os.environ.get('ZOHO_PASSWORD', '').strip()
HOST = os.environ.get('ZOHO_IMAP_HOST', 'imap.zoho.com').strip()
SENDER = os.environ.get('EXPECTED_SENDER', '').strip().lower()
FORCED_FOLDER = os.environ.get('IMAP_FOLDER', '').strip()

if not EMAIL or not PASSWORD:
    print("ERROR: faltan ZOHO_EMAIL o ZOHO_PASSWORD")
    sys.exit(1)
if not SENDER:
    print("ERROR: falta EXPECTED_SENDER")
    sys.exit(1)

print(f"Conectando a {HOST} como {EMAIL} ...")
M = imaplib.IMAP4_SSL(HOST)
try:
    M.login(EMAIL, PASSWORD)
except imaplib.IMAP4.error as e:
    print(f"ERROR de login: {e}")
    sys.exit(1)
print("Login OK.")


def parse_folder_line(line):
    """Extrae el nombre de la carpeta de una linea de IMAP LIST.
    Formato tipico: (\\HasNoChildren) "/" "INBOX"
    """
    if isinstance(line, bytes):
        try: line = line.decode('utf-8')
        except: line = line.decode('latin-1', errors='replace')
    # El nombre de la carpeta es lo ultimo entre comillas (o sin comillas si no hay espacios)
    m = re.search(r'"([^"]*)"\s*$', line)
    if m: return m.group(1)
    parts = line.rsplit(' ', 1)
    return parts[-1] if parts else None


def listar_folders():
    status, data = M.list()
    folders = []
    if status == 'OK':
        for line in data:
            f = parse_folder_line(line)
            if f: folders.append(f)
    return folders


def buscar_en(folder):
    """Selecciona la carpeta y busca mails del SENDER con adjunto .accdb.
    Devuelve (filename, bytes) o (None, None)."""
    try:
        # Algunos folders compartidos tienen espacios/caracteres especiales, hay que entrecomillar
        sel_name = '"' + folder.replace('"', '\\"') + '"' if (' ' in folder or '/' in folder) else folder
        status, _ = M.select(sel_name, readonly=True)
        if status != 'OK':
            return None, None
    except Exception as e:
        print(f"    no se pudo abrir {folder!r}: {str(e)[:80]}")
        return None, None
    status, data = M.search(None, f'FROM "{SENDER}"')
    if status != 'OK' or not data[0]:
        return None, None
    ids = data[0].split()
    print(f"    {len(ids)} mails de {SENDER!r} en esta carpeta")
    # iterar de mas reciente a mas viejo
    for mid in reversed(ids):
        status, msg_data = M.fetch(mid, '(RFC822)')
        if status != 'OK': continue
        msg = email.message_from_bytes(msg_data[0][1], policy=default)
        asunto = msg.get('Subject', '(sin asunto)')
        fecha = msg.get('Date', '')
        for part in msg.iter_attachments():
            fn = part.get_filename() or ''
            if fn.lower().endswith('.accdb'):
                body = part.get_payload(decode=True)
                print(f"    Mail: '{asunto}' del {fecha}")
                print(f"    Adjunto: {fn} ({len(body)//1024} KB)")
                return fn, body
    return None, None


# 1) listar todas las carpetas disponibles (incluye compartidas)
print("Carpetas disponibles en tu cuenta:")
folders = listar_folders()
for f in folders: print(f"  - {f}")

# 2) construir lista de carpetas a probar (en prioridad)
candidatas = []
if FORCED_FOLDER:
    candidatas = [FORCED_FOLDER]
else:
    # INBOX primero, despues cualquier carpeta que tenga "cotiz" o "compartido" en el nombre
    candidatas = ['INBOX']
    for f in folders:
        fl = f.lower()
        if f == 'INBOX': continue
        if 'cotiz' in fl or 'compartid' in fl or 'shared' in fl or 'administrador' in fl:
            candidatas.append(f)

print(f"\nProbando estas carpetas en orden: {candidatas}\n")

# 3) buscar en cada carpeta
encontrado_fn = None
encontrado_bytes = None
for folder in candidatas:
    print(f"  Buscando en {folder!r}...")
    fn, body = buscar_en(folder)
    if fn:
        encontrado_fn = fn
        encontrado_bytes = body
        print(f"  ENCONTRADO en {folder!r}")
        break

M.logout()

if not encontrado_fn:
    print("\nERROR: no se encontro ningun mail con .accdb en ninguna carpeta.")
    print("Posibles causas:")
    print("  1. EXPECTED_SENDER no coincide con el remitente real.")
    print("  2. El mail esta en una carpeta cuyo nombre no contiene 'cotiz' ni 'compartido'.")
    print("     En ese caso, agrega un secret IMAP_FOLDER con la ruta exacta (de la lista de arriba).")
    sys.exit(1)

with open('Cotizador-Latest.accdb', 'wb') as f:
    f.write(encontrado_bytes)
print(f"\nGuardado: Cotizador-Latest.accdb ({len(encontrado_bytes)//1024} KB)")
