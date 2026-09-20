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

echo "[startup] Aplicando migraciones..."
"${PYTHON_BIN}" gotogym/manage.py migrate --noinput

echo "[startup] Iniciando gunicorn..."
exec gunicorn --chdir gotogym gotogym.wsgi \
  --bind=0.0.0.0 \
  --timeout 600 \
  --access-logfile - \
  --error-logfile -
