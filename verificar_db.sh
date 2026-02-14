#!/bin/bash
# Script para verificar estado de bases de datos
# GoToGymPrime

echo "═══════════════════════════════════════════════════════"
echo "  🔍 VERIFICACIÓN DE BASES DE DATOS - GoToGymPrime"
echo "═══════════════════════════════════════════════════════"
echo ""

cd /workspaces/GoToGtymPrime/gotogym

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}📊 1. BASE DE DATOS LOCAL (SQLite)${NC}"
echo "───────────────────────────────────────────────────────"
if [ -f "db_local.sqlite3" ]; then
    echo -e "${GREEN}✅ Archivo existe${NC}"
    ls -lh db_local.sqlite3 | awk '{print "   Tamaño: " $5}'
    
    echo ""
    echo "📋 Contenido de la base de datos:"
    python manage.py shell --settings=gotogym.settings_local << 'EOF'
from accounts.models import User
from products.models import Product, ProductCategory, Brand

print(f"   👥 Usuarios: {User.objects.count()}")
print(f"   🛍️  Productos: {Product.objects.count()}")
print(f"   📦 Categorías: {ProductCategory.objects.count()}")
print(f"   🏷️  Marcas: {Brand.objects.count()}")

if User.objects.filter(is_superuser=True).exists():
    print(f"   ✅ Hay superusuarios")
else:
    print(f"   ⚠️  NO hay superusuarios")
EOF
else
    echo -e "${YELLOW}❌ No existe db_local.sqlite3${NC}"
    echo "   Ejecuta: python manage.py migrate --settings=gotogym.settings_local"
fi

echo ""
echo -e "${BLUE}📊 2. BASE DE DATOS PRODUCCIÓN (MySQL Azure)${NC}"
echo "───────────────────────────────────────────────────────"
echo "   Host: servergotogym.mysql.database.azure.com"
echo "   Base de datos: gotogym_bd"
echo "   Usuario: gotogym_user"
echo ""
echo "   Probando conexión..."
timeout 5 python manage.py check --database default --settings=gotogym.settings 2>&1 | head -5

echo ""
echo -e "${BLUE}🌐 3. SERVIDOR WEB${NC}"
echo "───────────────────────────────────────────────────────"
if pgrep -f "runserver" > /dev/null; then
    echo -e "${GREEN}✅ Servidor Django está corriendo${NC}"
    PID=$(pgrep -f "runserver" | head -1)
    echo "   PID: $PID"
    echo "   Puerto: 8000"
    
    # Verificar respuesta
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ 2>/dev/null)
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
        echo -e "   ${GREEN}✅ Respondiendo correctamente (HTTP $HTTP_CODE)${NC}"
    else
        echo -e "   ${YELLOW}⚠️  HTTP Status: $HTTP_CODE${NC}"
    fi
else
    echo -e "${YELLOW}❌ Servidor no está corriendo${NC}"
    echo "   Inicia con: python manage.py runserver 0.0.0.0:8000 --settings=gotogym.settings_local"
fi

echo ""
echo -e "${BLUE}🔗 4. URL DE ACCESO${NC}"
echo "───────────────────────────────────────────────────────"
if [ -n "$CODESPACE_NAME" ]; then
    CODESPACE_URL="https://${CODESPACE_NAME}-8000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
    echo -e "${GREEN}📱 URL Codespace:${NC}"
    echo "   $CODESPACE_URL"
    echo ""
    echo "   Panel Admin: $CODESPACE_URL/admin/"
    echo "   Login: admin@gotogym.com / admin123"
else
    echo "   http://localhost:8000/"
    echo "   Panel Admin: http://localhost:8000/es/admin/"
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ✅ Verificación completa"
echo "═══════════════════════════════════════════════════════"
