#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ROOT_DIR}/environments/frontend/.env.test"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

BASE_URL="${FRONTEND_BASE_URL:-http://localhost:8000}"
LOCALE_PREFIX="${FRONTEND_LOCALE_PREFIX:-es}"
LOGIN_PATH="${FRONTEND_LOGIN_PATH:-/accounts/login/}"
CATALOG_PATH="${FRONTEND_CATALOG_PATH:-/tienda/}"
PRODUCTS_PATH="${FRONTEND_PRODUCTS_PATH:-/products/products/}"
BLOG_PATH="${FRONTEND_BLOG_PATH:-/blog/}"

PATHS=("/" "${LOGIN_PATH}" "${CATALOG_PATH}" "${PRODUCTS_PATH}" "${BLOG_PATH}")

check_url() {
  local url="$1"
  local code
  code="$(curl -sS -o /dev/null -w "%{http_code}" "${url}")"
  if [[ "${code}" == "200" || "${code}" == "302" ]]; then
    echo "[frontend] OK ${url} -> HTTP ${code}"
    return 0
  fi
  return 1
}

for path in "${PATHS[@]}"; do
  url="${BASE_URL}${path}"
  if check_url "${url}"; then
    continue
  fi

  localized_url="${BASE_URL}/${LOCALE_PREFIX}${path}"
  if check_url "${localized_url}"; then
    continue
  fi

  echo "[frontend] ERROR ${url} y ${localized_url} no respondieron en 200/302"
  exit 1
done

echo "[frontend] Smoke tests finalizados correctamente."
