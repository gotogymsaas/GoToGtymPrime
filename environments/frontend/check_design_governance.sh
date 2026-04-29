#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BASELINE_FILE="${ROOT_DIR}/environments/frontend/design_baseline.env"

if [[ ! -f "${BASELINE_FILE}" ]]; then
  echo "[design-governance] ERROR: no se encontro ${BASELINE_FILE}"
  exit 1
fi

# shellcheck disable=SC1090
source "${BASELINE_FILE}"

if [[ -z "${MAX_HEX_IN_TEMPLATES:-}" ]]; then
  echo "[design-governance] ERROR: MAX_HEX_IN_TEMPLATES no definido en baseline"
  exit 1
fi

CURRENT_COUNT="$(rg -n "#[0-9A-Fa-f]{3,6}" "${ROOT_DIR}/gotogym/accounts/templates" "${ROOT_DIR}/gotogym/products/templates" "${ROOT_DIR}/gotogym/gotogym/templates" -g '*.html' | wc -l | tr -d ' ')"

echo "[design-governance] Baseline permitido: ${MAX_HEX_IN_TEMPLATES}"
echo "[design-governance] Conteo actual: ${CURRENT_COUNT}"

if (( CURRENT_COUNT > MAX_HEX_IN_TEMPLATES )); then
  echo "[design-governance] ERROR: aumentaron los colores hardcodeados en templates."
  echo "[design-governance] Reduce hex directos y usa tokens/clases del sistema en gotogym/static/css/style.css"
  exit 1
fi

echo "[design-governance] OK: no aumento la deuda de hardcoded colors."
