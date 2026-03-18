#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ROOT_DIR}/environments/azure/.env.release"
DRY_RUN="${DRY_RUN:-true}"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-92b318a9-86bc-4734-9cc9-821767f6084f}"
RESOURCE_GROUP="${AZURE_RELEASE_RESOURCE_GROUP:-gotogymweb}"
WEBAPP_NAME="${AZURE_RELEASE_WEBAPP:-gotogymweb}"
STAGING_SLOT="${AZURE_RELEASE_SLOT:-staging}"

required_env=(
  "DJANGO_SECRET_KEY"
  "DEBUG"
  "ALLOWED_HOSTS"
  "CORS_ALLOWED_ORIGINS"
  "MERCADOPAGO_ACCESS_TOKEN"
  "ALEGRA_API_TOKEN"
)

for var in "${required_env[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "[fase2-apply] ERROR: falta variable requerida ${var}"
    exit 1
  fi
done

run_cmd() {
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[fase2-apply] DRY_RUN az $*"
  else
    az "$@"
  fi
}

echo "[fase2-apply] Subscription objetivo: ${SUBSCRIPTION_ID}"
az account set --subscription "${SUBSCRIPTION_ID}"
state="$(az account show --query state -o tsv)"
if [[ "${state}" != "Enabled" ]]; then
  echo "[fase2-apply] ERROR: la suscripcion esta en estado ${state}."
  echo "[fase2-apply] ERROR: habilita la suscripcion antes de aplicar configuracion Fase 2."
  exit 2
fi

slot_count="$(az webapp deployment slot list -g "${RESOURCE_GROUP}" -n "${WEBAPP_NAME}" --query "[?contains(name, '/${STAGING_SLOT}')]|length(@)" -o tsv)"
if [[ "${slot_count}" == "0" ]]; then
  run_cmd webapp deployment slot create -g "${RESOURCE_GROUP}" -n "${WEBAPP_NAME}" --slot "${STAGING_SLOT}"
fi

startup_cmd="gunicorn --chdir gotogym gotogym.wsgi --bind=0.0.0.0 --timeout 600 --access-logfile '-' --error-logfile '-'"
run_cmd webapp config set -g "${RESOURCE_GROUP}" -n "${WEBAPP_NAME}" --startup-file "${startup_cmd}"

run_cmd webapp config appsettings set -g "${RESOURCE_GROUP}" -n "${WEBAPP_NAME}" --settings \
  DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY}" \
  DEBUG="${DEBUG}" \
  ALLOWED_HOSTS="${ALLOWED_HOSTS}" \
  CORS_ALLOWED_ORIGINS="${CORS_ALLOWED_ORIGINS}" \
  MERCADOPAGO_ACCESS_TOKEN="${MERCADOPAGO_ACCESS_TOKEN}" \
  ALEGRA_API_TOKEN="${ALEGRA_API_TOKEN}" \
  HUBSPOT_PRIVATE_TOKEN="${HUBSPOT_PRIVATE_TOKEN:-}"

run_cmd webapp log config -g "${RESOURCE_GROUP}" -n "${WEBAPP_NAME}" --application-logging filesystem --web-server-logging filesystem --level information

echo "[fase2-apply] Configuracion Fase 2 completada (DRY_RUN=${DRY_RUN})."
