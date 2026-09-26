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

echo "[startup] Recolectando estaticos..."
"${PYTHON_BIN}" gotogym/manage.py collectstatic --noinput

# Este script quedo desincronizado de lo que el App Service corria de
# verdad (el Startup Command configurado a mano en el Portal, invisible
# para git) el tiempo suficiente para provocar una caida: revertir este
# archivo no arreglaba nada porque Azure ni lo estaba ejecutando. La
# version de abajo es exactamente el comando que se verifico funcionando
# en produccion -- puerto, workers y timeout incluidos -- para que este
# archivo deje de ser documentacion aspiracional y vuelva a ser la fuente
# de verdad real.
echo "[startup] Iniciando gunicorn..."
exec gunicorn --chdir gotogym gotogym.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers 2 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
