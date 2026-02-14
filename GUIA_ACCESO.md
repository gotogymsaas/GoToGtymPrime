# 🚀 Guía de Acceso al Proyecto GoToGymPrime

## ✅ SERVIDOR ACTIVO Y LISTO PARA PROBAR

---

## 🌐 URLs de Acceso

### Desde tu Codespace (GitHub):
```
🔗 URL Principal: https://improved-space-eureka-9xp7w7qx4v937r7g-8000.app.github.dev/

📱 Página de inicio: https://improved-space-eureka-9xp7w7qx4v937r7g-8000.app.github.dev/
🔐 Panel Admin: https://improved-space-eureka-9xp7w7qx4v937r7g-8000.app.github.dev/admin/
🛍️ Productos: https://improved-space-eureka-9xp7w7qx4v937r7g-8000.app.github.dev/products/
```

### Credenciales de Admin:
```
Email: admin@gotogym.com
Password: admin123
```

**⚠️ IMPORTANTE:** VS Code/Codespaces puede pedirte hacer el puerto público la primera vez.
- Click en la pestaña "PORTS" (abajo)
- Click derecho en puerto 8000
- Selecciona "Port Visibility" → "Public"

---

## 💾 Bases de Datos del Proyecto

### 🟢 Base de Datos ACTUAL (Local - SQLite)
**Ubicación:** `/workspaces/GoToGtymPrime/gotogym/db_local.sqlite3`
**Estado:** ✅ Activa ahora
**Contenido:**
- ✅ 1 Superusuario creado
- ✅ 4 Productos de ejemplo
- ✅ 2 Categorías
- ✅ 1 Marca

#### Verificar contenido:
```bash
cd /workspaces/GoToGtymPrime/gotogym

# Ver usuarios
python manage.py shell --settings=gotogym.settings_local
>>> from accounts.models import User
>>> User.objects.all()
>>> exit()

# Ver productos
python manage.py dbshell --settings=gotogym.settings_local
sqlite> SELECT * FROM products_product;
sqlite> .exit
```

#### Ventajas SQLite Local:
- ✅ No necesitas conexión a Azure
- ✅ No afectas datos de producción
- ✅ Rápido para desarrollo
- ✅ Archivo simple que puedes borrar y recrear

---

### 🔵 Base de Datos de PRODUCCIÓN (MySQL Azure)
**Host:** `servergotogym.mysql.database.azure.com`
**Base de Datos:** `gotogym_bd`
**Estado:** ⚠️ Con migraciones inconsistentes

#### Para usar MySQL Azure:
```bash
cd /workspaces/GoToGtymPrime/gotogym

# Verificar conexión (solo lectura)
python manage.py dbshell --settings=gotogym.settings
```

**⚠️ NO RECOMENDADO para desarrollo:**
- Tiene datos reales/producción
- Estado de migraciones inconsistente
- Requiere conexión a Azure
- Cambios afectan a todos

---

## 📊 Cómo Verificar las Bases de Datos

### Opción 1: Django Admin (Interfaz Web)
```
1. Ve a: https://[tu-codespace]-8000.app.github.dev/es/admin/
2. Login: admin@gotogym.com / admin123
3. Explora:
   - Usuarios (Accounts > Users)
   - Productos (Products > Products)
   - Categorías (Products > Product categories)
   - Etc.
```

### Opción 2: Django Shell (Consola Python)
```bash
cd /workspaces/GoToGtymPrime/gotogym
python manage.py shell --settings=gotogym.settings_local

# Ejemplos de consultas:
>>> from accounts.models import User
>>> User.objects.count()  # Contar usuarios
>>> User.objects.all()    # Ver todos

>>> from products.models import Product
>>> Product.objects.count()  # Contar productos
>>> for p in Product.objects.all():
...     print(f"{p.name} - ${p.price}")
```

### Opción 3: Cliente SQL Directo
```bash
# SQLite
cd /workspaces/GoToGtymPrime/gotogym
sqlite3 db_local.sqlite3

# Comandos útiles:
.tables              # Ver todas las tablas
.schema products_product  # Ver estructura de tabla
SELECT * FROM products_product;
SELECT * FROM accounts_user;
.exit

# MySQL (Azure)
mysql -h servergotogym.mysql.database.azure.com \
      -u gotogym_user \
      -p gotogym_bd
```

### Opción 4: VS Code Extensions
Puedes instalar extensiones en tu codespace:
- **SQLite Viewer** - Para explorar db_local.sqlite3
- **MySQL** - Para conectarte a Azure

---

## 🖥️ ¿Dónde puedes ejecutar el proyecto?

### 1️⃣ **AQUÍ en Codespaces** (Recomendado) ✅
**Ventajas:**
- ✅ Ya está funcionando ahora
- ✅ No requiere instalación en tu PC
- ✅ Acceso desde cualquier navegador
- ✅ Entorno Linux completo
- ✅ Base de datos local incluida

**URL actual:**
```
https://improved-space-eureka-9xp7w7qx4v937r7g-8000.app.github.dev/
```

---

### 2️⃣ **En tu PC Windows/Mac/Linux**

#### Requisitos:
```bash
- Python 3.10+
- pip
- Git
```

#### Pasos:
```bash
# 1. Clonar el repositorio
git clone https://github.com/gotogymsaas/GoToGtymPrime.git
cd GoToGtymPrime

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 3. Instalar dependencias
pip install -r requirements.txt
pip install mysqlclient    # O: pip install PyMySQL

# 4. Migrar base de datos local
cd gotogym
python manage.py migrate --settings=gotogym.settings_local

# 5. Crear superusuario
python manage.py createsuperuser --settings=gotogym.settings_local

# 6. Arrancar servidor
python manage.py runserver --settings=gotogym.settings_local

# 7. Abrir navegador
# http://localhost:8000/
```

**Ventajas:**
- ✅ Desarrollo sin conexión
- ✅ Más rápido (local)
- ✅ Puedes usar tu IDE favorito

**Desventajas:**
- ❌ Requiere instalación de dependencias
- ❌ Posibles problemas de compatibilidad

---

### 3️⃣ **Desplegar en Azure** (Producción)

#### Para Azure Web App:
```bash
# Ver documentación de Django en Azure:
https://docs.microsoft.com/azure/app-service/quickstart-python

# Pasos básicos:
1. Crear Azure Web App (Python 3.12)
2. Configurar variables de entorno
3. Conectar con GitHub Actions
4. Deploy automático desde main branch
```

**Cuándo usar:**
- Para producción/clientes
- Necesitas HTTPS y dominio
- Múltiples usuarios concurrentes

**⚠️ No recomendado para pruebas/desarrollo**

---

## 🎯 Recomendación Personal

### Para PROBAR y DESARROLLAR:
👉 **Usa Codespaces (donde estás ahora)**
- Ya funciona
- Base de datos local limpia
- No rompes nada de producción

### Para DESPLEGAR a usuarios reales:
👉 **Azure u otro hosting**
- Configura MySQL de producción
- Variables de entorno seguras
- HTTPS habilitado

---

## 🧪 Comandos Útiles para Probar

### Ver logs del servidor:
```bash
# En otra terminal
cd /workspaces/GoToGtymPrime/gotogym
tail -f nohup.out  # Si usaste nohup
```

### Reiniciar servidor:
```bash
# Detener
pkill -f runserver

# Reiniciar
cd /workspaces/GoToGtymPrime/gotogym
python manage.py runserver 0.0.0.0:8000 --settings=gotogym.settings_local
```

### Resetear base de datos:
```bash
cd /workspaces/GoToGtymPrime/gotogym
rm db_local.sqlite3
python manage.py migrate --settings=gotogym.settings_local
python manage.py createsuperuser --settings=gotogym.settings_local
```

### Ver estado de la base de datos:
```bash
cd /workspaces/GoToGtymPrime/gotogym

# Tamaño de la DB
ls -lh db_local.sqlite3

# Tablas creadas
python manage.py dbshell --settings=gotogym.settings_local
sqlite> .tables
sqlite> .exit
```

---

## 📍 URLs Importantes del Proyecto

```
/                           → Página principal (redirige a /es/ automáticamente)
/admin/                     → Panel de administración
/accounts/login/            → Login de usuarios
/accounts/register/         → Registro de usuarios
/products/                  → Catálogo de productos
/carrito/                   → Carrito de compras
/blog/                      → Blog
/dashboard/                 → Dashboard (requiere login)
/configuracion-marca/       → Configuración de marca
/setlang/                   → Cambiar idioma (es/en/pt)
```

---

## ✅ Estado Actual

- 🟢 Servidor: **Corriendo** en puerto 8000
- 🟢 Base de datos: **SQLite local** con datos de prueba
- 🟢 Superusuario: **Creado** (admin@gotogym.com)
- 🟢 Productos: **4 productos** de ejemplo cargados
- 🟢 Migraciones: **Aplicadas** correctamente

**¡Listo para probar!** 🚀
