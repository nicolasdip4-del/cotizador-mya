#!/usr/bin/env python3
"""Genera Cotizador.html (-> index.html) a partir de un .accdb.

Modo CI: lee COTIZADOR_PASSWORD del env y la inyecta como hash SHA-256
en el password gate del HTML."""
import sys, os, glob, json, datetime, collections, base64, hashlib
import urllib.request, ssl, functools

print = functools.partial(print, flush=True)

print("Iniciando actualizar.py ...")

try:
    from access_parser import AccessParser
except ImportError:
    print("Instalando access-parser...")
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--quiet', 'access-parser'])
    from access_parser import AccessParser

print("access_parser OK.")

MIN_BUNDLE_BYTES = 30 * 1024
PWD_SALT = 'mya-cot-salt-2026'


def calcular_pwd_hash():
    pwd = os.environ.get('COTIZADOR_PASSWORD', '').strip()
    if not pwd:
        print("  (sin COTIZADOR_PASSWORD: el HTML va sin gate)")
        return ''
    h = hashlib.sha256((PWD_SALT + pwd).encode('utf-8')).hexdigest()
    print(f"  password gate activado (hash {h[:8]}...)")
    return h


def _bundle_es_stub(text):
    if not text: return True
    head = text[:600]
    return ('import "/' in head) or ('import"/' in head)


def cargar_mdb_reader_bundle(directorio):
    cache = os.path.join(directorio, 'mdb-reader-bundle.js')
    if os.path.exists(cache):
        try:
            sz = os.path.getsize(cache)
            with open(cache, 'r', encoding='utf-8') as f:
                data = f.read()
            if sz > MIN_BUNDLE_BYTES and not _bundle_es_stub(data):
                print(f"  mdb-reader: usando cache local ({sz//1024} KB)")
                return data
        except Exception: pass
    urls = [
        'https://cdn.jsdelivr.net/npm/mdb-reader@3/+esm',
        'https://esm.run/mdb-reader@3',
        'https://esm.sh/mdb-reader@3?bundle-deps',
    ]
    ctx = ssl.create_default_context()
    for url in urls:
        try:
            print(f"  mdb-reader: bajando {url} ...")
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 actualizar.py'})
            with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
                body = r.read().decode('utf-8')
            if len(body) >= MIN_BUNDLE_BYTES and not _bundle_es_stub(body):
                with open(cache, 'w', encoding='utf-8') as f: f.write(body)
                print(f"  mdb-reader: OK ({len(body)//1024} KB)")
                return body
        except Exception as e:
            print(f"    fallo: {str(e)[:120]}")
    print("  AVISO: mdb-reader no embebido. Va a usar CDN en runtime.")
    return ''


def safe_get(col, i):
    try: return col[i]
    except (IndexError, KeyError, TypeError): return None


def min_len(d, keys):
    valids = [len(d[k]) for k in keys if k in d and d[k] is not None]
    return min(valids) if valids else 0


def extraer_datos(ruta):
    print("Leyendo:", ruta)
    db = AccessParser(ruta)

    ig = db.parse_table('InfoGlobal')
    listas = []
    for i in range(min_len(ig, ['CodLista','NomLista'])):
        try:
            cod = safe_get(ig['CodLista'], i)
            if cod is None: continue
            listas.append({
                'cod': int(cod),
                'nombre': safe_get(ig.get('NomLista', []), i) or '',
                'desde': (safe_get(ig.get('desde', []), i) or '')[:10],
                'hasta': (safe_get(ig.get('hasta', []), i) or '')[:10],
                'facIVA': float(safe_get(ig.get('FacIVA', []), i) or 0),
                'ahora3': float(safe_get(ig.get('Ahora3', []), i) or 0),
                'ahora6': float(safe_get(ig.get('Ahora6', []), i) or 0),
            })
        except Exception: continue
    print(f"  InfoGlobal: {len(listas)} listas")

    lp = db.parse_table('lprecio')
    prod_idx, visto, skipped = {}, set(), 0
    n_lp = min_len(lp, ['codigo','cod_alfa','precio','stock','IVA','CodLista','detalle','linea_prod'])
    for i in range(n_lp):
        try:
            ca = safe_get(lp.get('cod_alfa', []), i)
            cl_raw = safe_get(lp.get('CodLista', []), i)
            if ca is None or cl_raw is None: skipped += 1; continue
            cl = int(cl_raw or 0)
            if not ca or (ca, cl) in visto: continue
            visto.add((ca, cl))
            if ca not in prod_idx:
                prod_idx[ca] = {
                    'cod_alfa': ca,
                    'detalle': safe_get(lp.get('detalle', []), i) or '',
                    'linea': safe_get(lp.get('linea_prod', []), i) or 'SIN DEFINIR',
                    'iva': float(safe_get(lp.get('IVA', []), i) or 0),
                    'novedad': int(safe_get(lp.get('Novedad', []), i) or 0),
                    'precios': {},
                }
            prod_idx[ca]['precios'][str(cl)] = {
                'p': float(safe_get(lp.get('precio', []), i) or 0),
                's': int(safe_get(lp.get('stock', []), i) or 0),
                'a3': float(safe_get(lp.get('Ahora3', []), i) or 0),
                'a6': float(safe_get(lp.get('Ahora6', []), i) or 0),
            }
        except Exception: skipped += 1
    productos = list(prod_idx.values())
    print(f"  lprecio: {len(productos)} productos unicos")

    t = db.parse_table('Tarjetas')
    tarjetas = []
    for i in range(min_len(t, ['idTarjeta','Ncuotas','Inc_Cobr'])):
        try:
            iid = safe_get(t.get('idTarjeta', []), i)
            if iid is None: continue
            tarjetas.append({
                'id': int(iid),
                'marca': safe_get(t.get('TARJETAS', []), i) or '',
                'banco': safe_get(t.get('Banco', []), i) or '',
                'cuotas': int(safe_get(t.get('Ncuotas', []), i) or 0),
                'rec': float(safe_get(t.get('Inc_Cobr', []), i) or 1),
                'coef': float(safe_get(t.get('Coeficiente', []), i) or 1),
                'plan': safe_get(t.get('Cuotas', []), i) or '',
            })
        except Exception: continue
    print(f"  Tarjetas: {len(tarjetas)}")

    c = db.parse_table('Cheques')
    cheques = []
    for i in range(min_len(c, ['IdCheques','Cuotas'])):
        try:
            iid = safe_get(c.get('IdCheques', []), i)
            if iid is None: continue
            cheques.append({
                'id': int(iid),
                'plan': safe_get(c.get('Plan', []), i) or '',
                'cuotas': int(safe_get(c.get('Cuotas', []), i) or 0),
                'rec': float(safe_get(c.get('RecargoChq', []), i) or 0),
            })
        except Exception: continue
    print(f"  Cheques: {len(cheques)}")

    cv = db.parse_table('condven')
    condven = []
    for i in range(min_len(cv, ['codigo','cuotas','nombre'])):
        try:
            cod = safe_get(cv.get('codigo', []), i)
            if cod is None: continue
            condven.append({
                'cod': int(cod or 0),
                'nombre': safe_get(cv.get('nombre', []), i) or '',
                'descuento': float(safe_get(cv.get('descuento', []), i) or 0),
                'recargo': float(safe_get(cv.get('recargo', []), i) or 0),
                'cuotas': int(safe_get(cv.get('cuotas', []), i) or 0),
                'r_fin': float(safe_get(cv.get('r_financie', []), i) or 0),
            })
        except Exception: continue
    print(f"  condven: {len(condven)}")

    v = db.parse_table('Vendedores')
    por_area = collections.Counter()
    for i in range(min_len(v, ['codigo','nom_area'])):
        try: por_area[safe_get(v.get('nom_area', []), i)] += 1
        except Exception: continue
    vendedores = [{'area': k or '(sin zona)', 'n': c} for k, c in por_area.most_common()]
    print(f"  Vendedores: {sum(por_area.values())}")

    total_skus = len(productos)
    total_combos = sum(len(p['precios']) for p in productos)
    neg_prices = sum(1 for p in productos for x in p['precios'].values() if x['p'] < 0)
    zero_prices = sum(1 for p in productos for x in p['precios'].values() if x['p'] == 0)
    zero_stock = sum(1 for p in productos for x in p['precios'].values() if x['s'] <= 0)
    neg_stock = sum(1 for p in productos for x in p['precios'].values() if x['s'] < 0)
    por_linea = collections.Counter(p['linea'] for p in productos)
    val_lista = collections.defaultdict(float)
    for p in productos:
        for cl, info in p['precios'].items():
            if info['p'] > 0 and info['s'] > 0:
                val_lista[cl] += info['p'] * info['s']

    return {
        'generado': datetime.date.today().isoformat(),
        'archivo_origen': os.path.basename(ruta),
        'listas': listas, 'productos': productos, 'tarjetas': tarjetas,
        'cheques': cheques, 'condven': condven, 'vendedores': vendedores,
        'kpis': {
            'total_skus': total_skus, 'total_combos': total_combos,
            'neg_prices': neg_prices, 'zero_prices': zero_prices,
            'zero_stock': zero_stock, 'neg_stock': neg_stock,
            'por_linea': dict(por_linea),
            'val_lista': {k: v for k, v in val_lista.items()},
        },
    }


LOGO_MIMES = {'.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.gif':'image/gif','.webp':'image/webp'}


def cargar_logo_dataurl(directorio):
    for nombre in ['LOGO MYA.svg','LOGO MYA.png','LOGO MYA.jpg',
                   'logo.svg','logo.png','logo.jpg',
                   'LOGO.svg','LOGO.png','LOGO.jpg',
                   'Logo.svg','Logo.png','Logo.jpg']:
        ruta = os.path.join(directorio, nombre)
        if os.path.exists(ruta):
            ext = os.path.splitext(nombre)[1].lower()
            mime = LOGO_MIMES.get(ext, 'application/octet-stream')
            with open(ruta, 'rb') as f: raw = f.read()
            b64 = base64.b64encode(raw).decode('ascii')
            print(f"  Logo encontrado: {nombre} ({mime}, {len(raw)//1024} KB)")
            return f'data:{mime};base64,{b64}'
    print("  (Sin logo)")
    return ''


def generar_html(data, ruta_salida, dir_logo):
    aqui = os.path.dirname(os.path.abspath(__file__))
    plantilla = os.path.join(aqui, 'plantilla.html')
    with open(plantilla, 'r', encoding='utf-8') as f: html = f.read()
    html = html.replace('/*__DATA__*/null',
                        json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    html = html.replace('/*__LOGO_DATAURL__*/', cargar_logo_dataurl(dir_logo))
    html = html.replace('/*__LOGO__*/', '')
    html = html.replace('/*__MDB_READER_SOURCE__*/""',
                        json.dumps(cargar_mdb_reader_bundle(dir_logo)))
    html = html.replace('/*__PWD_HASH__*/', calcular_pwd_hash())
    with open(ruta_salida, 'w', encoding='utf-8') as f: f.write(html)
    print(f"OK: {ruta_salida} ({os.path.getsize(ruta_salida)//1024} KB)")


def main():
    if len(sys.argv) > 1:
        ruta = sys.argv[1]
    else:
        candidatos = sorted(glob.glob("*.accdb"), key=os.path.getmtime, reverse=True)
        if not candidatos:
            print("No hay .accdb en el directorio"); sys.exit(1)
        ruta = candidatos[0]
    if not os.path.exists(ruta):
        print("No existe:", ruta); sys.exit(1)
    data = extraer_datos(ruta)
    dir_base = os.path.dirname(os.path.abspath(ruta)) or '.'
    # CI: el output va al directorio del script (mismo que plantilla.html)
    out_dir = os.path.dirname(os.path.abspath(__file__))
    salida = os.path.join(out_dir, 'index.html' if os.environ.get('CI') else 'Cotizador.html')
    generar_html(data, salida, dir_base if os.path.exists(os.path.join(dir_base, 'LOGO MYA.svg')) or os.path.exists(os.path.join(dir_base, 'LOGO MYA.png')) else out_dir)
    print("Listo.")


if __name__ == '__main__':
    main()
