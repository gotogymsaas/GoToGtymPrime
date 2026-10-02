#!/usr/bin/env bash
# Validacion local equivalente al job `build` del CI, para que un error de
# lint, tipos, migraciones o pruebas se vea ANTES de subir el commit.
#
# Uso:
#   bash environments/backend/validate_local.sh           # completa (pre-push)
#   bash environments/backend/validate_local.sh --quick   # solo lo barato (pre-commit)
#
# Reproduce los mismos pasos que `run_backend_checks.sh` y el workflow, pero
# usando el Python del entorno actual (o el de `.venv`) en vez de crear un
# entorno virtual y reinstalar dependencias en cada corrida.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODE="${1:-full}"

# En Windows la consola usa cp1252 y algunos settings imprimen emojis; sin
# esto Python falla al escribir en la salida estandar.
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
cd "${ROOT_DIR}"

# Python: el del entorno virtual del proyecto si existe; si no, el del PATH.
if [[ -x "${ROOT_DIR}/.venv/Scripts/python.exe" ]]; then
  PY="${ROOT_DIR}/.venv/Scripts/python.exe"
elif [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  PY="${ROOT_DIR}/.venv/bin/python"
else
  PY="python"
fi

ENV_FILE="${ROOT_DIR}/environments/backend/.env.test"
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

fail() {
  echo ""
  echo "[validate] ERROR: $1"
  echo "[validate] Esto mismo haria fallar el build en GitHub. Corrigelo antes de subir."
  echo "[validate] (Saltar la validacion, bajo tu responsabilidad: git commit/push --no-verify)"
  exit 1
}

for tool in ruff mypy; do
  if ! "${PY}" -m "${tool}" --version >/dev/null 2>&1; then
    fail "falta '${tool}' en el entorno. Instala las dependencias: ${PY} -m pip install -r requirements-dev.txt"
  fi
done

echo "[validate] ruff (lint)..."
"${PY}" -m ruff check gotogym || fail "ruff encontro errores de lint (puedes aplicar los arreglos automaticos con: ${PY} -m ruff check gotogym --fix)."

echo "[validate] gobernanza de diseno (colores hexadecimales en plantillas)..."
bash "${ROOT_DIR}/environments/frontend/check_design_governance.sh" >/dev/null \
  || fail "aumentaron los colores hardcodeados en plantillas (ver environments/frontend/check_design_governance.sh)."

if [[ "${MODE}" == "--quick" ]]; then
  echo "[validate] OK (rapida)."
  exit 0
fi

echo "[validate] mypy (tipos)..."
DJANGO_SETTINGS_MODULE=gotogym.settings_test "${PY}" -m mypy gotogym || fail "mypy encontro errores de tipos."

cd "${ROOT_DIR}/gotogym"

echo "[validate] django check..."
"${PY}" manage.py check --settings=gotogym.settings_local >/dev/null || fail "'manage.py check' fallo."

echo "[validate] migraciones pendientes..."
"${PY}" manage.py makemigrations --check --dry-run --settings=gotogym.settings_test >/dev/null \
  || fail "hay cambios de modelos sin migracion (ejecuta: ${PY} manage.py makemigrations)."

echo "[validate] pruebas (settings_test)..."
"${PY}" manage.py test . administracion --settings=gotogym.settings_test \
  || fail "fallaron pruebas."

echo "[validate] OK: el build local pasa."
