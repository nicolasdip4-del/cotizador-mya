#!/usr/bin/env python3
"""Baja 'Hoja1' (central, todas las sucursales) del Sheet que escribe stock_sync.py
en Oracle -- ya trae 'Disponible Real' calculada por ese mismo script -- y genera
stock_global.json, que actualizar.py embebe en el cotizador."""
import json
import os
import sys

import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = os.environ.get('STOCK_SHEET_ID', '1IDstNIcIta3XLDiFFmdoxjCuARJwEKDSJi-oueq5Q8I')
WORKSHEET_NAME = 'Hoja1'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']


def _credentials():
    raw = os.environ.get('STOCKSYNC_CREDENTIALS_JSON')
    if raw:
        info = json.loads(raw)
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    path = os.environ.get('STOCKSYNC_CREDENTIALS_FILE', 'stocksync.json')
    if os.path.exists(path):
        return Credentials.from_service_account_file(path, scopes=SCOPES)
    raise SystemExit('Faltan credenciales: STOCKSYNC_CREDENTIALS_JSON o STOCKSYNC_CREDENTIALS_FILE')


def main():
    creds = _credentials()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.worksheet(WORKSHEET_NAME)
    rows = ws.get_all_records()
    print(f"Leidas {len(rows)} filas de '{WORKSHEET_NAME}'")

    out = []
    sucursales = set()
    for r in rows:
        codalfa = str(r.get('codalfa', '')).strip()
        if not codalfa:
            continue
        try:
            stock = int(float(r.get('stock', 0) or 0))
            disp_real = int(float(r.get('Disponible Real', 0) or 0))
        except (TypeError, ValueError):
            continue
        suc = (r.get('nom_area', '') or '').strip()
        sucursales.add(suc)
        out.append({
            'a': suc,
            'c': codalfa,
            'd': (r.get('detalle', '') or '').strip(),
            's': stock,
            'r': disp_real,
        })

    print(f"Sucursales: {sorted(sucursales)}")
    salida = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stock_global.json')
    with open(salida, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    print(f"OK: {salida} ({len(out)} filas, {os.path.getsize(salida)//1024} KB)")


if __name__ == '__main__':
    main()
