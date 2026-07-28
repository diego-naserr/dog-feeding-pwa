# Turno de Comida - Perros

PWA instalable (sin App Store/Play Store) para que la familia sepa a quién
le toca darle comida a los perros cada día, reciba un push a las 20:00 hora
de Chile si no está marcado, y cualquiera pueda dejar registro de quién lo
hizo y a qué hora.

- **Backend**: Python + FastAPI + SQLite (un solo archivo).
- **Frontend**: HTML/JS vanilla + manifest + service worker (sin build step).
- **Push**: Web Push estándar con VAPID (funciona en iOS 16.4+ y Android).
- **Rotación**: día de semana fijo, configurable en [`backend/app/config.py`](backend/app/config.py).

## 1. Correr localmente

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python generate_vapid_keys.py   # ver paso 2
# copiar la salida a backend/.env (junto a VAPID_SUBJECT)

python make_icons.py            # genera los íconos (solo la primera vez)

uvicorn app.main:app --reload --port 8000
```

Abrir `http://localhost:8000` en el navegador. La base SQLite se crea sola
en `backend/data/app.db` la primera vez que corre.

> Nota: los push reales requieren HTTPS (o `localhost`, que el navegador
> trata como seguro). Para probar notificaciones de punta a punta hace
> falta el despliegue en Railway (paso 3) o un túnel HTTPS local.

## 2. Generar las VAPID keys

Las VAPID keys identifican a tu servidor ante los navegadores para poder
mandar push sin depender de Firebase ni ningún servicio externo.

```bash
cd backend
source .venv/bin/activate
python generate_vapid_keys.py
```

Esto imprime algo así:

```
VAPID_PUBLIC_KEY=BBEs3Bp...
VAPID_PRIVATE_KEY=XC3KmZ...
VAPID_SUBJECT=mailto:tu-email@ejemplo.com
```

- Guardalas en `backend/.env` para desarrollo local (ese archivo está en
  `.gitignore`, nunca se sube al repo).
- En producción van como **Variables** del servicio en Railway (paso 3).
- Se generan **una sola vez** para todo el proyecto — no hay que
  regenerarlas en cada despliegue (si lo hacés, todas las suscripciones
  push existentes quedan inválidas y cada persona tendría que volver a
  aceptar notificaciones).

## 3. Desplegar en Railway

El repo está armado para correr como **un solo servicio**: FastAPI sirve
tanto la API (`/api/...`) como los archivos estáticos de la PWA.

### 3.1 Subir el código a GitHub

```bash
cd dog-feeding-pwa
git init
git add backend README.md
git commit -m "Turno de comida - PWA inicial"
git branch -M main
git remote add origin <URL-de-tu-repo-vacío-en-GitHub>
git push -u origin main
```

### 3.2 Crear el proyecto en Railway

1. En [railway.app](https://railway.app) → **New Project** → **Deploy from
   GitHub repo** → elegir este repo.
2. En **Settings** del servicio, setear **Root Directory** = `backend`
   (ahí están `requirements.txt` y el `Procfile`). Railway detecta Python
   automáticamente y usa el `Procfile` (`web: uvicorn app.main:app --host
   0.0.0.0 --port $PORT`).
3. En **Variables**, agregar:
   - `VAPID_PUBLIC_KEY`
   - `VAPID_PRIVATE_KEY`
   - `VAPID_SUBJECT` (ej. `mailto:tu-email@ejemplo.com`)
   - `DATABASE_PATH` = `/data/app.db`
4. **Importante — persistencia de SQLite**: el filesystem de Railway es
   efímero entre deploys. Andá a **Volumes** → **Add Volume**, montalo en
   `/data`. Sin esto, la base de datos (y el historial) se borra cada vez
   que se hace un nuevo deploy.
5. Deploy. Railway te da una URL pública tipo
   `https://tu-proyecto.up.railway.app` — **esa URL debe tener HTTPS**
   (Railway lo da gratis por defecto), es obligatorio para que Web Push
   funcione en el navegador.

### 3.3 Verificar

- `https://tu-proyecto.up.railway.app/api/today` debe devolver JSON.
- `https://tu-proyecto.up.railway.app/` debe cargar la PWA.

## 4. Instalar la PWA en el celular

### iPhone (Safari, iOS 16.4+)

1. Abrir la URL de Railway en **Safari** (tiene que ser Safari, no Chrome).
2. Tocar el ícono de compartir (el cuadrado con la flecha hacia arriba).
3. Elegir **"Agregar a inicio"**.
4. Abrir la app desde el ícono en la pantalla de inicio (no desde Safari)
   y aceptar el permiso de notificaciones cuando lo pida.

### Android (Chrome)

1. Abrir la URL de Railway en **Chrome**.
2. Tocar el menú (⋮) → **"Agregar a pantalla de inicio"** / **"Instalar
   app"**.
3. Confirmar. Abrir la app desde el ícono nuevo y aceptar el permiso de
   notificaciones.

### Primer uso

Al abrir por primera vez, la app pregunta **"¿Quién eres?"** — cada persona
elige su nombre en su propio dispositivo. Con eso queda asociada la
suscripción push a esa persona en ese teléfono, para que el aviso de las
20:00 le llegue a quien le toca ese día.

## Ajustes — todo se edita desde la app

La pestaña **Ajustes** (⚙️, abajo a la derecha) permite, sin tocar código
ni volver a desplegar:

- **Sos vos** — cambiar de identidad en cualquier momento, ver si las
  notificaciones están activas en ese dispositivo, y mandarse una
  notificación de prueba para confirmar que realmente llegan.
- **Personas** — agregar gente nueva, elegirles un color, renombrarlas, y
  desactivarlas (se conserva su historial; no se puede desactivar a
  alguien que todavía tiene días asignados en la rotación).
- **Rotación semanal** — quién le toca cada día de la semana.
- **Horarios de aviso** — hay dos:
  1. **Aviso principal**, solo para quien le toca ese día (por defecto 20:00).
  2. **Si nadie marcó, avisar a todos**, un segundo aviso que llega a
     *todos* si a esa hora nadie marcó que le dio de comer (por defecto
     21:30). "A tiempo" en el historial se calcula contra este horario.
  3. **Link del grupo de WhatsApp** (opcional) — si lo configurás, el
     segundo aviso lleva directo al grupo al tocarlo, y aparece un botón
     "Abrir grupo de WhatsApp" en la pantalla de Hoy.

En el día a día también hay un botón **Deshacer** en la pantalla de Hoy,
por si alguien marca por error que ya le dieron de comer.

[`backend/app/config.py`](backend/app/config.py) solo se usa como punto de
partida la primera vez que arranca la app (para no empezar con la base de
datos vacía). Después de ese primer arranque, editar ese archivo ya no
tiene efecto — todo vive en la base de datos y se edita desde Ajustes.
