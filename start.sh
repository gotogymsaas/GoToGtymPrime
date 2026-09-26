#!/bin/bash
# Script de inicio rápido para GoToGymPrime
# Autor: Análisis automatizado
# Fecha: 2026-02-14

set -e

echo "🚀 GoToGymPrime - Script de Inicio"
echo "=================================="
echo ""

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Directorio del proyecto: relativo a este script, no una ruta fija de un
# devcontainer especifico (la ruta absoluta anterior solo existia en un
# Codespace concreto y rompia el script en cualquier otro lugar).
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/gotogym" && pwd)"

# Verificar dependencias
echo "📦 Verificando dependencias..."
if ! command -v python &> /dev/null; then
    echo -e "${RED}❌ Python no está instalado${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Dependencias OK${NC}"
echo ""

# Navegar al directorio del proyecto
cd "$PROJECT_DIR"

# Verificar configuración (settings_local: SQLite, sin depender de
# variables de entorno de produccion que no existen en desarrollo)
echo "🔍 Verificando configuración..."
python manage.py check --settings=gotogym.settings_local
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Configuración válida${NC}"
else
    echo -e "${RED}❌ Error en configuración${NC}"
    exit 1
fi
echo ""

# Verificar migraciones
echo "🗄️  Verificando migraciones..."
PENDING=$(python manage.py showmigrations --plan --settings=gotogym.settings_local | grep "\[ \]" | wc -l)
if [ "$PENDING" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Hay $PENDING migraciones pendientes${NC}"
    read -p "¿Deseas aplicar las migraciones ahora? (s/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        echo "Aplicando migraciones..."
        python manage.py migrate --settings=gotogym.settings_local
        echo -e "${GREEN}✅ Migraciones aplicadas${NC}"
    else
        echo -e "${YELLOW}⚠️  Continuando sin aplicar migraciones${NC}"
    fi
else
    echo -e "${GREEN}✅ Todas las migraciones están aplicadas${NC}"
fi
echo ""

# Verificar superusuario
echo "👤 Verificando superusuario..."
HAS_SUPER=$(python manage.py shell --settings=gotogym.settings_local -c "from accounts.models import User; print(User.objects.filter(is_superuser=True).exists())")
if [ "$HAS_SUPER" = "False" ]; then
    echo -e "${YELLOW}⚠️  No hay superusuarios creados${NC}"
    read -p "¿Deseas crear un superusuario ahora? (s/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        python manage.py createsuperuser --settings=gotogym.settings_local
    fi
fi
echo ""

# Mostrar información de URLs
echo "📍 URLs importantes:"
echo "   - Frontend: http://localhost:8000/"
echo "   - Admin: http://localhost:8000/admin/"
echo ""

# Iniciar servidor
echo "🌐 Iniciando servidor de desarrollo..."
echo -e "${GREEN}Servidor corriendo en http://0.0.0.0:8000/${NC}"
echo -e "${YELLOW}Presiona Ctrl+C para detener${NC}"
echo ""

python manage.py runserver 0.0.0.0:8000 --settings=gotogym.settings_local
