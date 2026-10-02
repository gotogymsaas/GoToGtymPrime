#!/bin/bash
# Verifica el estado de la base de datos local y del servidor de desarrollo.
#
#   bash verificar_db.sh
#
# Es de solo lectura: no modifica datos. La base de produccion (PostgreSQL)
# se consulta con la configuracion por defecto, que lee DATABASE_URL del
# entorno; si no esta definida, usa SQLite y el resultado no dice nada sobre
# produccion.

# Directorio del proyecto: relativo a este script.
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/gotogym" && pwd)"
cd "$PROJECT_DIR" || exit 1

# Windows (Git Bash) usa cp1252 por defecto y algunos mensajes llevan emojis.
export PYTHONUTF8=1

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "═══════════════════════════════════════════════════════"
echo "  Verificación de bases de datos y servidor - GoToGymPrime"
echo "═══════════════════════════════════════════════════════"
echo ""

echo -e "${BLUE}1. Base de datos local (SQLite)${NC}"
echo "───────────────────────────────────────────────────────"
if [ -f "db_local.sqlite3" ]; then
    echo -e "${GREEN}Archivo existe${NC}"
    ls -lh db_local.sqlite3 | awk '{print "   Tamaño: " $5}'
    echo ""
    python manage.py shell --settings=gotogym.settings_local << 'EOF'
from accounts.models import User
from blog.models import Post
from orders.models import Order
from products.models import Brand, Product, ProductCategory

print(f"   Usuarios:    {User.objects.count()}")
print(f"   Productos:   {Product.objects.count()}")
print(f"   Categorías:  {ProductCategory.objects.count()}")
print(f"   Marcas:      {Brand.objects.count()}")
print(f"   Pedidos:     {Order.objects.count()}")
print(f"   Entradas del Journal: {Post.objects.filter(is_published=True).count()}")
print("   Hay superusuarios" if User.objects.filter(is_superuser=True).exists() else "   NO hay superusuarios (createsuperuser)")
EOF
    echo ""
    echo "   Para una auditoría de integridad del catálogo:"
    echo "   python manage.py audit_catalog --settings=gotogym.settings_local"
else
    echo -e "${YELLOW}No existe db_local.sqlite3${NC}"
    echo "   Ejecuta: python manage.py migrate --settings=gotogym.settings_local"
fi

echo ""
echo -e "${BLUE}2. Base de datos de producción (PostgreSQL)${NC}"
echo "───────────────────────────────────────────────────────"
if [ -n "$DATABASE_URL" ]; then
    echo "   DATABASE_URL definida; probando conexión..."
    timeout 10 python manage.py check --database default 2>&1 | head -5
else
    echo -e "${YELLOW}   DATABASE_URL no está definida en este entorno.${NC}"
    echo "   Sin ella la configuración por defecto usa SQLite, así que esta revisión"
    echo "   no habla de producción. Defínela para probar la conexión real."
fi

echo ""
echo -e "${BLUE}3. Servidor de desarrollo${NC}"
echo "───────────────────────────────────────────────────────"
ENCONTRADO=0
for PUERTO in 8000 8001; do
    CODIGO=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${PUERTO}/healthz" 2>/dev/null)
    if [ "$CODIGO" = "200" ]; then
        echo -e "${GREEN}Servidor respondiendo en http://localhost:${PUERTO}/ (HTTP ${CODIGO})${NC}"
        ENCONTRADO=1
    fi
done
if [ "$ENCONTRADO" = "0" ]; then
    echo -e "${YELLOW}No hay un servidor respondiendo en los puertos 8000 ni 8001.${NC}"
    echo "   Inicia con: EJECUTAR_LOCAL.bat (Windows) o ./start.sh"
fi

echo ""
echo -e "${BLUE}4. Dónde entrar${NC}"
echo "───────────────────────────────────────────────────────"
echo "   Tienda:          http://localhost:8000/es/"
echo "   Panel interno:   http://localhost:8000/es/admin-panel/"
echo "   Admin de Django: http://localhost:8000/es/admin/"
echo ""
echo "Guía completa: docs/GUIA_ACCESO.md"
