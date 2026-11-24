#!/usr/bin/env bash
set -euo pipefail

# Oryx comprime el build en output.tar.zst y lo extrae al arrancar el
# contenedor. Este script corre ya dentro de esa copia extraida, que es el
# unico lugar donde conviven el codigo, el virtualenv y las app settings.
PYTHON_BIN="$(command -v python || command -v python3)"

echo "[startup] cwd=$(pwd)"
echo "[startup] python=${PYTHON_BIN}"

if [ ! -f gotogym/manage.py ]; then
  echo "[startup] ERROR: no se encontro gotogym/manage.py"
  ls -la
  exit 1
fi

# `migrate` es el del proyecto (afiliados/management/commands/migrate.py): si
# la base viene de cuando el programa se llamaba "influencer", antes de migrar
# renombra sus tablas y registros a "afiliados" (ver afiliados/adaptar_base.py).
# En una base ya adaptada o nueva no hace nada. Conviene un respaldo de la base
# antes del primer despliegue que incluya este cambio.
echo "[startup] Aplicando migraciones..."
"${PYTHON_BIN}" gotogym/manage.py migrate --noinput

echo "[startup] Recolectando estaticos..."
"${PYTHON_BIN}" gotogym/manage.py collectstatic --noinput

# Entradas del Journal: son datos, no codigo, asi que no llegan con el
# despliegue. --solo-faltantes crea las que no existen y nunca pisa las que
# ya estan (ni sus ediciones). Un fallo aqui no debe impedir que el sitio
# arranque.
echo "[startup] Cargando entradas del Journal (solo las que faltan)..."
"${PYTHON_BIN}" gotogym/manage.py seed_journal --solo-faltantes   || echo "[startup] AVISO: no se pudieron cargar las entradas del Journal; el sitio arranca igual."

# Este es el comando de arranque versionado y recomendado. El Startup Command
# que ejecuta el App Service se configura en el Portal de Azure y git no lo
# ve: solo ejecuta este archivo si alguien con acceso al Portal lo configuro
# como `bash environments/azure/startup.sh`. Mientras eso no este confirmado,
# produccion puede seguir corriendo la version anterior (migrate, collectstatic
# y gunicorn con 2 workers sincronos y timeout 120, sin seed_journal). Ver
# docs/DESPLIEGUE.md, "Pendientes que requieren acceso a Azure".
#
# gunicorn con hilos (gthread): 2 procesos x 8 hilos atienden 16 peticiones a
# la vez. Una peticion lenta (el Coach, el correo, Alegra) ocupa un hilo y no
# un proceso entero. Cada hilo mantiene su propia conexion a PostgreSQL
# (DB_CONN_MAX_AGE), asi que el maximo en regimen es workers x threads = 16;
# ver el calculo completo en docs/DESPLIEGUE.md antes de subir estos valores.
# Los valores viven solo aqui: el Dockerfile ejecuta este mismo script.
echo "[startup] Iniciando gunicorn..."
exec gunicorn --chdir gotogym gotogym.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --worker-class gthread \
  --workers 2 \
  --threads 8 \
  --timeout 60 \
  --error-logfile -
