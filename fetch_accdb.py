#!/usr/bin/env python3
"""Descarga el .accdb mas reciente desde Zoho IMAP.

Variables de entorno requeridas (vienen de GitHub Secrets):
  ZOHO_EMAIL         - tu direccion de mail en Zoho
  ZOHO_PASSWORD      - tu password de Zoho (o app password)
  EXPECTED_SENDER    - mail del remitente que envia el .accdb (filtro)
  ZOHO_IMAP_HOST     - opcional. Default: imap.zoho.com
                        (si tu cuenta es .eu o .in usar imap.zoho.eu, imap.zoho.in)
"""
import os, sys, email, imaplib, functools
from email.policy import default

print = functools.partial(print, flush=True)

EMAIL = os.environ.get('ZOHO_EMAIL', '').strip()
PASSWORD = os.environ.get('ZOHO_PASSWORD', '').strip()
HOST = os.environ.get('ZOHO_IMAP_HOST', 'imap.zoho.com').strip()
SENDER = os.environ.get('EXPECTED_SENDER', '').strip().lower()

if not EMAIL or not PASSWORD:
    print("ERROR: faltan ZOHO_EMAIL o ZOHO_PASSWORD en el environment")
    sys.exit(1)
if not SENDER:
    print("ERROR: falta EXPECTED_SENDER en el environment")
    sys.exit(1)

print(f"Conectando a {HOST} como {EMAIL} ...")
M = imaplib.IMAP4_SSL(HOST)
try:
    M.login(EMAIL, PASSWORD)
except imaplib.IMAP4.error as e:
    print(f"ERROR de login: {e}")
    print("Verifica ZOHO_EMAIL/ZOHO_PASSWORD. Si tu Zoho tiene 2FA, usa una App Password.")
    sys.exit(1)
M.select('INBOX')

print(f"Buscando mails de '{SENDER}' con adjunto .accdb ...")
status, data = M.search(None, f'FROM "{SENDER}"')
if status != 'OK' or not data[0]:
    print(f"No se encontraron mails de {SENDER}")
    M.logout()
    sys.exit(1)
ids = data[0].split()
print(f"  {len(ids)} mails de ese remitente. Recorriendo de mas nuevo a mas viejo ...")

encontrado_nombre = None
encontrado_bytes = None
for mid in reversed(ids):
    status, msg_data = M.fetch(mid, '(RFC822)')
    if status != 'OK': continue
    msg = email.message_from_bytes(msg_data[0][1], policy=default)
    asunto = msg.get('Subject', '(sin asunto)')
    fecha = msg.get('Date', '')
    for part in msg.iter_attachments():
        fn = part.get_filename() or ''
        if fn.lower().endswith('.accdb'):
            encontrado_nombre = fn
            encontrado_bytes = part.get_payload(decode=True)
            print(f"  Mail: '{asunto}' del {fecha}")
            print(f"  Adjunto: {fn} ({len(encontrado_bytes)//1024} KB)")
            break
    if encontrado_nombre:
        break

M.logout()

if not encontrado_nombre:
    print(f"ERROR: ninguno de los {len(ids)} mails de {SENDER} tenia adjunto .accdb")
    sys.exit(1)

with open('Cotizador-Latest.accdb', 'wb') as f:
    f.write(encontrado_bytes)
print(f"Guardado como Cotizador-Latest.accdb ({len(encontrado_bytes)//1024} KB)")
