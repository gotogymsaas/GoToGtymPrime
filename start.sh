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

# Directorio del proyecto
PROJECT_DIR="/workspaces/GoToGtymPrime/gotogym"

# Verificar dependencias
echo "📦 Verificando dependencias..."
if ! command -v python &> /dev/null; then
    echo -e "${RED}❌ Python no está instalado${NC}"
    exit 1
fi

if ! pip show mysqlclient &> /dev/null; then
    echo -e "${YELLOW}⚠️  Instalando mysqlclient...${NC}"
    pip install mysqlclient
fi

echo -e "${GREEN}✅ Dependencias OK${NC}"
echo ""

# Navegar al directorio del proyecto
cd "$PROJECT_DIR"

# Verificar configuración
echo "🔍 Verificando configuración..."
python manage.py check
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Configuración válida${NC}"
else
    echo -e "${RED}❌ Error en configuración${NC}"
    exit 1
fi
echo ""

# Verificar migraciones
echo "🗄️  Verificando migraciones..."
PENDING=$(python manage.py showmigrations --plan | grep "\[ \]" | wc -l)
if [ "$PENDING" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Hay $PENDING migraciones pendientes${NC}"
    read -p "¿Deseas aplicar las migraciones ahora? (s/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        echo "Aplicando migraciones..."
        python manage.py migrate
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
HAS_SUPER=$(python manage.py shell -c "from accounts.models import User; print(User.objects.filter(is_superuser=True).exists())")
if [ "$HAS_SUPER" = "False" ]; then
    echo -e "${YELLOW}⚠️  No hay superusuarios creados${NC}"
    read -p "¿Deseas crear un superusuario ahora? (s/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        python manage.py createsuperuser
    fi
fi
echo ""

# Mostrar información de URLs
echo "📍 URLs importantes:"
echo "   - Frontend: http://localhost:8000/"
echo "   - Admin: http://localhost:8000/admin/"
echo "   - API métricas: http://localhost:8000/crm/"
echo ""

# Iniciar servidor
echo "🌐 Iniciando servidor de desarrollo..."
echo -e "${GREEN}Servidor corriendo en http://0.0.0.0:8000/${NC}"
echo -e "${YELLOW}Presiona Ctrl+C para detener${NC}"
echo ""

python manage.py runserver 0.0.0.0:8000
