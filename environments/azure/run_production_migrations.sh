#!/usr/bin/env bash
set -euo pipefail

if [ -f antenv/bin/activate ]; then
  # shellcheck disable=SC1091
  source antenv/bin/activate
fi

if [ -f manage.py ]; then
  python3 manage.py migrate --noinput
elif [ -f gotogym/manage.py ]; then
  cd gotogym
  python3 manage.py migrate --noinput
else
  echo "manage.py no encontrado; estructura real de $(pwd):"
  find . -maxdepth 3 -iname manage.py
  ls -la .
  exit 2
fi
