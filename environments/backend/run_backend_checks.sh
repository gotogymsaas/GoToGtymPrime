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

echo "[backend] Comprobando migraciones pendientes..."
python manage.py makemigrations --check --dry-run --settings=gotogym.settings_test

echo "[backend] Ejecutando django check --deploy con la configuracion de produccion simulada..."
# Sin DEBUG y con una clave secreta y una base de datos declaradas, que es
# lo que ve `settings.py` en el App Service. Los avisos HSTS que el sitio
# decidio no activar estan silenciados en el modulo de verificacion.
DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(60))')" \
DATABASE_URL="postgresql://usuario:clave@localhost:5432/gotogym" \
  python manage.py check --deploy --fail-level WARNING \
  --settings=gotogym.settings_verificacion_despliegue

echo "[backend] Ejecutando la suite completa con cobertura (settings_test)..."
# Todo lo que el descubrimiento encuentra: un cambio en cualquier app se
# prueba antes de llegar a main. `TEST_PARALLEL` fija los procesos: 2 en
# local (la maquina de desarrollo tiene poca CPU) y uno por nucleo en el CI.
if [[ -z "${TEST_PARALLEL:-}" ]]; then
  if [[ "${CI:-}" == "true" ]]; then TEST_PARALLEL=auto; else TEST_PARALLEL=2; fi
fi
coverage erase --rcfile="${ROOT_DIR}/pyproject.toml"
coverage run --rcfile="${ROOT_DIR}/pyproject.toml" manage.py test . \
  --parallel "${TEST_PARALLEL}" --settings=gotogym.settings_test
coverage combine --rcfile="${ROOT_DIR}/pyproject.toml"
# `COVERAGE_FAIL_UNDER` es el piso de cobertura. Se fija con el valor medido
# en una corrida completa y solo se sube cuando sube la cobertura.
coverage report --rcfile="${ROOT_DIR}/pyproject.toml" \
  ${COVERAGE_FAIL_UNDER:+--fail-under="${COVERAGE_FAIL_UNDER}"}

echo "[backend] Validaciones finalizadas."
