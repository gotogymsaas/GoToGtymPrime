#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv-backend-test"
ENV_FILE="${ROOT_DIR}/environments/backend/.env.test"

if [[ ! -d "${VENV_DIR}" ]]; then
  python3 -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r "${ROOT_DIR}/requirements.txt"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

cd "${ROOT_DIR}/gotogym"

echo "[backend] Ejecutando django check (settings_local)..."
python manage.py check --settings=gotogym.settings_local

echo "[backend] Ejecutando test suite (settings_test)..."
python manage.py test --settings=gotogym.settings_test

echo "[backend] Validaciones finalizadas."
