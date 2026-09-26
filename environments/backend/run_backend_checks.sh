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
python -m pip install -r "${ROOT_DIR}/requirements-dev.txt"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

echo "[backend] Ejecutando ruff (lint)..."
ruff check "${ROOT_DIR}/gotogym"

echo "[backend] Ejecutando mypy (tipos)..."
# El backlog inicial (17 errores reales, ver historial de pyproject.toml)
# ya se corrigio: esto bloquea el build igual que ruff.
(cd "${ROOT_DIR}" && DJANGO_SETTINGS_MODULE=gotogym.settings_test mypy gotogym)

cd "${ROOT_DIR}/gotogym"

echo "[backend] Ejecutando django check (settings_local)..."
python manage.py check --settings=gotogym.settings_local

echo "[backend] Ejecutando test suite con cobertura (settings_test)..."
# `manage.py test` sin argumentos solo descubre pruebas dentro del arbol de
# este directorio (gotogym/). `administracion` vive fisicamente aqui mismo
# (gotogym/administracion/), pero fuera del paquete raiz gotogym.gotogym,
# por lo que se agrega como etiqueta explicita para que el discovery la
# encuentre. Se ejecutan ambos grupos en el mismo proceso y sobre la misma
# base de pruebas: separarlos podia ocultar errores de orden, fixtures o
# estado compartido entre apps y no reproducía la suite combinada que usa
# la validacion de PR.
coverage run --rcfile="${ROOT_DIR}/pyproject.toml" manage.py test . administracion --settings=gotogym.settings_test
coverage report --rcfile="${ROOT_DIR}/pyproject.toml"

echo "[backend] Validaciones finalizadas."
