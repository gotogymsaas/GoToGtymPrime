#!/usr/bin/env bash
# Activa los hooks versionados en `.githooks/` para este clon del repositorio.
# Se ejecuta una sola vez por clon:  bash environments/install_git_hooks.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

git config core.hooksPath .githooks
chmod +x .githooks/* environments/backend/validate_local.sh 2>/dev/null || true

echo "Hooks activados (core.hooksPath = .githooks):"
echo "  pre-commit -> lint + gobernanza de diseno (rapido)"
echo "  pre-push   -> validacion completa equivalente al build del CI"
