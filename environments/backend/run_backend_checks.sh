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

echo "[backend] Ejecutando import-linter (dependencias entre apps)..."
(cd "${ROOT_DIR}/gotogym" && PYTHONPATH=. lint-imports --config ../pyproject.toml)

echo "[backend] Ejecutando mypy (tipos)..."
# El backlog inicial (17 errores reales, ver historial de pyproject.toml)
# ya se corrigio: esto bloquea el build igual que ruff.
(cd "${ROOT_DIR}" && DJANGO_SETTINGS_MODULE=gotogym.settings_test mypy gotogym)

cd "${ROOT_DIR}/gotogym"

echo "[backend] Ejecutando django check (settings_local)..."
python manage.py check --settings=gotogym.settings_local

echo "[backend] Ejecutando test suite con cobertura (settings_test)..."
# La validacion de despliegue cubre el camino que puede causar perdida de
# dinero o acceso: autenticacion, checkout, inventario, pedidos, pagos,
# integraciones, permisos y configuracion de seguridad. La suite completa
# permanece disponible para regresion (`FULL_TEST_SUITE=true`) y no se borra
# por el solo hecho de no ser necesaria en cada deploy.
if [[ "${FULL_TEST_SUITE:-false}" == "true" ]]; then
  test_labels=(. administracion)
  echo "[backend] FULL_TEST_SUITE=true: ejecutando todos los tests descubiertos."
else
  test_labels=(
    accounts.tests
    carrito.tests
    inventory.tests
    orders.tests
    payments.tests
    products.tests
    shipping.tests
    integrations.test_clients
    gotogym.test_errores
  )
  echo "[backend] Suite esencial: ${#test_labels[@]} modulos criticos sin descubrimiento recursivo."
fi
coverage run --rcfile="${ROOT_DIR}/pyproject.toml" manage.py test "${test_labels[@]}" --settings=gotogym.settings_test
coverage report --rcfile="${ROOT_DIR}/pyproject.toml"

echo "[backend] Validaciones finalizadas."
