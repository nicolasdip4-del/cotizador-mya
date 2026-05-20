# Cotizador M&A - version web automatica

Este repo se actualiza solo todas las mañanas a las 9:00 AM Argentina, bajando
el `.accdb` mas reciente desde tu Zoho mail y regenerando `index.html`.

Netlify sirve `index.html` y queda online en `https://<algun-nombre>.netlify.app`.

## Setup inicial (una sola vez)

### 1. Crear el repo en GitHub
1. Andate a github.com y crea un repo nuevo: `cotizador-mya` (puede ser **privado**).
2. Subi todos los archivos de esta carpeta al repo (drag-and-drop en la web vale).
3. **Importante**: subi tambien `LOGO MYA.svg` (o .png) si querés que aparezca.

### 2. Configurar los GitHub Secrets
En el repo, anda a **Settings -> Secrets and variables -> Actions -> New repository secret**.
Agrega estos 5 secrets:

| Nombre | Valor |
| --- | --- |
| `ZOHO_EMAIL` | Tu mail en Zoho (ej. `sebastian@miempresa.com.ar`) |
| `ZOHO_PASSWORD` | Tu password de Zoho |
| `ZOHO_IMAP_HOST` | `imap.zoho.com` (o `.eu` / `.in` segun tu region) |
| `EXPECTED_SENDER` | Mail del remitente que envia el .accdb diariamente |
| `COTIZADOR_PASSWORD` | La clave que los vendedores tendran que ingresar para acceder |

> Si tu Zoho tiene 2FA activado, en lugar de tu password normal creas una
> **App Password** en Zoho -> Mi cuenta -> Seguridad -> Application-Specific Passwords.

### 3. Probar el workflow manualmente
1. En el repo, anda a la pestaña **Actions**.
2. Click en "Actualizar Cotizador desde Zoho".
3. Boton "Run workflow" -> Run workflow.
4. Espera 1-2 minutos. Si esta verde -> exito. Si esta rojo -> mira los logs.
5. Verifica que `index.html` aparecio en el repo.

### 4. Conectar Netlify
1. Andate a netlify.com y crea cuenta (free).
2. **Add new site -> Import an existing project -> GitHub** -> elegi tu repo `cotizador-mya`.
3. Build settings: dejar todo vacio, **Publish directory = `.`** (un punto).
4. Click **Deploy**.
5. En 30 segundos vas a tener una URL `https://random-name-123.netlify.app`.
6. Compartila con tus vendedores (con la clave que pusiste en `COTIZADOR_PASSWORD`).

### 5. Listo
A partir de mañana a las 9 AM (AR), el cotizador se actualiza solo.

## Como funciona

```
9:00 AM AR (12:00 UTC)
  -> GitHub Action arranca
  -> fetch_accdb.py se conecta a Zoho IMAP
  -> Busca el mail mas reciente de EXPECTED_SENDER con adjunto .accdb
  -> Lo guarda como Cotizador-Latest.accdb
  -> actualizar.py genera index.html embeddando datos + logo + mdb-reader + password gate
  -> Si index.html cambio, git push
  -> Netlify detecta el push y re-deploya en ~30 segundos
```

## Tunear

- **Cambiar el horario**: edita `.github/workflows/refresh.yml`, linea con `cron: '0 12 * * *'`.
  El formato es `min hour * * *` en UTC. Ejemplo `'0 11 * * *'` = 8 AM AR.
- **Forzar actualizacion ahora**: ve a Actions -> Run workflow.
- **Cambiar password**: edita el secret `COTIZADOR_PASSWORD` y corre Run workflow.
- **Ver logs**: pestaña Actions del repo, click en la corrida que te interese.

## Problemas frecuentes

**El workflow falla en "Bajar el .accdb desde Zoho"**:
- Verifica que `ZOHO_PASSWORD` sea correcto (si tenes 2FA, debe ser App Password).
- Verifica que `EXPECTED_SENDER` coincida exactamente con el remitente real.
- Mira los logs en Actions para ver el mensaje de error.

**El HTML no muestra el logo**:
- Subi `LOGO MYA.svg` (o `.png`) a la raiz del repo y commitea.
- Corre Run workflow.

**Los vendedores ven "Clave incorrecta"**:
- Confirma con ellos que estan tipeando exactamente la clave de `COTIZADOR_PASSWORD`.
- Si quieres cambiarla, editas el secret y corres Run workflow.
