#!/usr/bin/env bash
set -uo pipefail

SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-c6015f72-55d5-4282-ba0b-f02152d798f7}"
RESOURCE_GROUP="${AZURE_RELEASE_RESOURCE_GROUP:-rg-gotogym-prime}"
WEBAPP_NAME="${AZURE_RELEASE_WEBAPP:-gotogym-prime}"
STAGING_SLOT="${AZURE_RELEASE_SLOT:-staging}"

required_settings=(
  "DJANGO_SECRET_KEY"
  "DEBUG"
  "ALLOWED_HOSTS"
  "CORS_ALLOWED_ORIGINS"
  "DATABASE_URL"
  "CSRF_TRUSTED_ORIGINS"
  "MERCADOPAGO_ACCESS_TOKEN"
  "ALEGRA_API_TOKEN"
)

run_or_warn() {
  local title="$1"
  shift
  echo "[azure-preflight] ${title}"
  if ! "$@"; then
    echo "[azure-preflight] WARNING: no fue posible completar '${title}'."
    return 0
  fi
}

echo "[azure-preflight] Subscription objetivo: ${SUBSCRIPTION_ID}"
az account set --subscription "${SUBSCRIPTION_ID}"
az account show --query "{name:name,id:id,state:state,tenantId:tenantId}" -o table

account_state="$(az account show --query state -o tsv)"
if [[ "${account_state}" != "Enabled" ]]; then
  echo "[azure-preflight] WARNING: la suscripcion no esta Enabled (${account_state})."
  echo "[azure-preflight] WARNING: operaciones de escritura o algunas lecturas pueden fallar."
fi

run_or_warn "Web App objetivo" az webapp show -g "${RESOURCE_GROUP}" -n "${WEBAPP_NAME}" --query "{name:name,state:state,defaultHostName:defaultHostName,location:location,kind:kind}" -o table

run_or_warn "Configuracion runtime/startup" az webapp config show -g "${RESOURCE_GROUP}" -n "${WEBAPP_NAME}" --query "{linuxFxVersion:linuxFxVersion,appCommandLine:appCommandLine,alwaysOn:alwaysOn,http20Enabled:http20Enabled}" -o table

echo "[azure-preflight] Verificando slot staging"
slot_count="$(az webapp deployment slot list -g "${RESOURCE_GROUP}" -n "${WEBAPP_NAME}" --query "[?contains(name, '/${STAGING_SLOT}')]|length(@)" -o tsv 2>/dev/null || echo "0")"
if [[ "${slot_count}" == "1" ]]; then
  echo "[azure-preflight] OK: slot ${STAGING_SLOT} existe."
else
  echo "[azure-preflight] WARNING: slot ${STAGING_SLOT} no existe."
  echo "[azure-preflight] Sugerencia: az webapp deployment slot create -g ${RESOURCE_GROUP} -n ${WEBAPP_NAME} --slot ${STAGING_SLOT}"
fi

run_or_warn "Gobernanza: policy assignments" az policy assignment list --query "[].{name:name,scope:scope,enforcementMode:enforcementMode}" -o table
run_or_warn "Gobernanza: locks" az lock list --query "[].{name:name,level:level,resourceGroup:resourceGroup}" -o table

echo "[azure-preflight] App settings requeridas"
tmp_file="$(mktemp)"
if az webapp config appsettings list -g "${RESOURCE_GROUP}" -n "${WEBAPP_NAME}" --query "[].name" -o tsv > "${tmp_file}" 2>/dev/null; then
  missing=0
  for key in "${required_settings[@]}"; do
    if grep -qx "${key}" "${tmp_file}"; then
      echo "[azure-preflight] OK setting: ${key}"
    else
      echo "[azure-preflight] MISSING setting: ${key}"
      missing=1
    fi
  done
  if [[ "${missing}" -eq 1 ]]; then
    echo "[azure-preflight] WARNING: hay app settings faltantes."
  fi
else
  echo "[azure-preflight] WARNING: no fue posible listar app settings (posible restriccion por estado de suscripcion o permisos)."
fi
rm -f "${tmp_file}"

echo "[azure-preflight] Preflight finalizado."
