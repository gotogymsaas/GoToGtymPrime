#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bash "${ROOT_DIR}/environments/backend/run_backend_checks.sh"

source "${ROOT_DIR}/.venv-backend-test/bin/activate"
cd "${ROOT_DIR}/gotogym"
python manage.py runserver 127.0.0.1:8000 --settings=gotogym.settings_local > /tmp/gotogym-smoke.log 2>&1 &
DJANGO_PID=$!
trap 'kill $DJANGO_PID || true' EXIT
sleep 6

cd "${ROOT_DIR}"
bash "${ROOT_DIR}/environments/frontend/run_frontend_smoke.sh"

echo "[all-checks] Backend + frontend validados correctamente."
