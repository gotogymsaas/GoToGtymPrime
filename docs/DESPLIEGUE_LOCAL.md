# 🚀 Guía de Despliegue Local - GoToGymPrime

## 🧭 Checklist Maestro de Ejecución (Azure)

Este documento será la bitácora oficial hasta completar el objetivo de release.

### Reglas operativas activas

1. Documentar cada avance, decisión y validación en este archivo.
2. Hacer commit + push en cada respuesta para asegurar trazabilidad continua.
3. No ejecutar cambios destructivos sin aprobación explícita.
4. No avanzar de fase sin criterio de salida cumplido.

### Estado por fases

| Fase | Objetivo | Estado | Criterio de salida |
|------|----------|--------|--------------------|
| F0 | Definir entorno único de release | ✅ Completada (inicial) | RG y recursos objetivo definidos |
| F1 | Estabilización P0 (arranque/seguridad base) | ✅ Completada | App inicia y configuración crítica saneada |
| F2 | Infra mínima Azure lista | 🔄 En progreso | App Service + variables + logs listos |
| F3 | Pipeline de despliegue validado | 🔄 En progreso | Build/deploy con fallas bloqueantes |
| F4 | Primer despliegue controlado | ⏳ Pendiente | Health/login/catálogo/checkout OK |
| F5 | Cierre de release y rollback | ⏳ Pendiente | Checklist final + plan rollback validado |

### Bitácora de ejecución

#### 2026-03-18 — Fase 0 (definición de entorno)

- Suscripción evaluada: `92b318a9-86bc-4734-9cc9-821767f6084f`.
- Entorno objetivo seleccionado para este release: `gotogymweb`.
- Justificación: es el entorno ya cableado al workflow actual y minimiza riesgo de cambio simultáneo.
- Recursos asociados detectados:
    - Resource Group: `gotogymweb`
    - Web App: `gotogymweb`
    - App Service Plan: `ASP-gotogymweb-9d8a`
    - MySQL Flexible Server relacionado: `gotogymwebserver`
- Gap identificado para fases siguientes:
    - no se detectó slot `staging` en la suscripción actual.

#### 2026-03-18 — Fase 1 (estabilización P0) progreso inicial

- Ajustes aplicados:
    - Corrección de arranque Gunicorn en Docker con `--chdir gotogym` y logs a stdout/stderr.
    - Endurecimiento inicial de `settings.py` para producción:
        - `DEBUG` por defecto en `false`.
        - `ALLOWED_HOSTS` desde variable de entorno (sin `*` por defecto).
        - `CORS_ALLOW_ALL_ORIGINS` desactivado por defecto y lista de orígenes explícita.
        - eliminación de password MySQL hardcodeada por defecto.
    - Variables críticas expuestas en settings para runtime:
        - `MERCADOPAGO_ACCESS_TOKEN`
        - `HUBSPOT_PRIVATE_TOKEN`
        - `ALEGRA_API_TOKEN` con fallback a `ALEGRA_TOKEN`.
    - Workflow de GitHub Actions actualizado con `startup-command` explícito para App Service Linux.
- Validación ejecutada:
    - `python -m py_compile gotogym/gotogym/settings.py` ✅
    - `bash environments/backend/run_backend_checks.sh` ✅
        - crea `.venv-backend-test`
        - instala dependencias desde `requirements.txt`
        - ejecuta `python manage.py check --settings=gotogym.settings_local` sin errores
        - ejecuta suite de tests actual (`NO TESTS RAN`, cobertura pendiente)
- Estado F1:
    - sigue en progreso hasta validar arranque funcional con dependencias instaladas y completar checklist P0.

#### 2026-03-18 — Auditoría Azure RBAC/Gobernanza + GitHub/Extensiones

- Azure RBAC (suscripción `92b318a9-86bc-4734-9cc9-821767f6084f`):
    - Se detectaron asignaciones con `roleDefinitionId` `de139f84-1756-47ae-9be6-808fbbe84772` en recursos `gotogymweb` y `gotogym-prod-rg`.
    - El ID corresponde al rol **Website Contributor** (validado por `az role definition list`).
    - Consulta completa de role assignments quedó parcialmente bloqueada por token de Graph en Cloud Shell (`Timeout waiting for token from portal`).
- Gobernanza:
    - Policy assignment activo: `SecurityCenterBuiltIn` (ASC Default) a nivel suscripción, enforcement `Default`.
    - No se observaron locks en la consulta actual (`az lock list` sin salida).
    - Hallazgo operativo: la suscripción aparece en estado de solo lectura para algunas operaciones (`ReadOnlyDisabledSubscription`).
- Integración GitHub <-> Azure detectada en `gotogymweb`:
    - `isGitHubAction: true`
    - `repoUrl: https://github.com/gotogymsaas/GoToGtymPrime`
    - Rama: `main`
    - Auth type: `oidc`
    - Runtime: `python 3.13`
- Integraciones de aplicación detectadas en código:
    - `integrations/alegra` (facturación/contabilidad)
    - `integrations/mercadopago` (checkout/pagos)
    - `integrations/hubspot` (CRM, implementación parcial)
- GitHub CLI local:
    - `gh` instalado, pero no autenticado (`gh auth status` solicita login).
- Extensiones instaladas relevantes para operación:
    - `github.copilot-chat`
    - `ms-azuretools.azure-dev`
    - `ms-azuretools.vscode-azure-github-copilot`
    - `ms-azuretools.vscode-azure-mcp-server`
    - `ms-azuretools.vscode-azureresourcegroups`
    - `ms-azuretools.vscode-containers`

#### 2026-03-18 — Entornos de pruebas backend/frontend (implementación)

- Se crea carpeta `environments/` con separación explícita:
    - `environments/backend/` para validaciones Django y pruebas backend.
    - `environments/frontend/` para smoke tests de vistas frontend (templates Django).
- Entregables de esta fase:
    - plantillas `.env.test.example` backend/frontend.
    - scripts `run_backend_checks.sh` y `run_frontend_smoke.sh`.
    - guía de ejecución de entornos en `environments/README.md`.
- Validación de ejecución:
    - smoke frontend ejecutado con backend local levantado: ✅
    - rutas validadas: `/`, `/accounts/login/`, `/tienda/`, `/products/products/`, `/blog/`
- Nota de arquitectura:
    - el frontend actual del repositorio es SSR con templates Django; no hay app Node/Next.js activa en este checkout.

#### 2026-03-18 — Fase 2 (infra mínima Azure) avance

- Se agrega preflight ejecutable para infraestructura objetivo:
    - `environments/azure/run_fase2_preflight.sh`
- Cobertura del preflight:
    - estado de suscripción
    - estado/configuración del Web App
    - verificación de slot staging
    - policy assignments y locks
    - presencia de app settings críticas
- Objetivo inmediato:
    - correr este preflight antes de cualquier intento de despliegue final y registrar salida en esta bitácora.
- Resultado de ejecución del preflight:
    - suscripción detectada en estado `Warned`.
    - operaciones sobre Web App con error `ReadOnlyDisabledSubscription`.
    - slot `staging` no existe actualmente.
    - policy assignment activo confirmado: `SecurityCenterBuiltIn`.
    - listado de app settings críticas no disponible por restricción actual de suscripción/permisos.
- Implicación de release:
    - Fase 2 no puede cerrarse hasta habilitar suscripción y completar configuración de settings en App Service.

#### 2026-03-18 — Fase 3 (pipeline) avance

- Workflow `main_gotogymweb.yml` actualizado con quality gates en build:
    - ejecución de `environments/backend/run_backend_checks.sh`
    - `migrate` + `collectstatic` con `settings_local`
    - smoke tests frontend con `environments/frontend/run_frontend_smoke.sh`
- Condición de avance:
    - el deploy se ejecuta solo si build valida backend/frontend correctamente.
- Pendiente para cierre F3:
    - observar una ejecución real del workflow en GitHub Actions para confirmar semáforo verde end-to-end.

---

## 📋 Requisitos Previos

- **Python:** 3.10 o superior
- **pip:** Gestor de paquetes de Python
- **Git:** Para clonar el repositorio
- **SQLite:** Ya incluido en Python (para desarrollo)
- **MySQL Client:** Solo si vas a usar MySQL

---

## 🔧 Instalación en Local (Windows/Mac/Linux)

### 1. Clonar el Repositorio

```bash
git clone https://github.com/gotogymsaas/GoToGtymPrime.git
cd GoToGtymPrime
```

### 2. Crear Entorno Virtual

**En Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**En Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
```

### 3. Instalar Dependencias

```bash
pip install --upgrade pip
pip install -r requirements.txt

# Instalar driver MySQL (opcional, solo si usarás MySQL)
pip install mysqlclient
```

**⚠️ Problemas con mysqlclient en Windows:**
```cmd
# Si falla mysqlclient, usa PyMySQL como alternativa:
pip install PyMySQL
```

### 4. Configurar Base de Datos Local

El proyecto incluye configuración automática para SQLite (desarrollo local):

```bash
cd gotogym

# Crear base de datos y aplicar migraciones
python manage.py migrate --settings=gotogym.settings_local

# Verificar que se creó la base de datos
ls -lh db_local.sqlite3
```

### 5. Crear Usuario Administrador

```bash
python manage.py createsuperuser --settings=gotogym.settings_local

# Se te pedirá:
# - Email (ej: admin@ejemplo.com)
# - Username (ej: admin)
# - Password (crea una contraseña segura)
```

### 6. Cargar Datos de Ejemplo (Opcional)

```bash
python manage.py shell --settings=gotogym.settings_local
```

Luego copia y pega este código:

```python
from products.models import Product, ProductCategory, Brand
from decimal import Decimal

# Crear categorías
cat_ropa, _ = ProductCategory.objects.get_or_create(
    name="Ropa Deportiva",
    defaults={'description': 'Ropa para entrenar'}
)
cat_acces, _ = ProductCategory.objects.get_or_create(
    name="Accesorios",
    defaults={'description': 'Accesorios de gym'}
)

# Crear marca
brand, _ = Brand.objects.get_or_create(name="GoToGym")

# Crear productos
products = [
    {"name": "Camiseta Deportiva", "category": cat_ropa, "price": "29.99", "stock": 50},
    {"name": "Pantalón de Yoga", "category": cat_ropa, "price": "39.99", "stock": 30},
    {"name": "Botella de Agua", "category": cat_acces, "price": "12.99", "stock": 100},
    {"name": "Toalla de Gym", "category": cat_acces, "price": "15.99", "stock": 75},
    {"name": "Guantes de Entrenamiento", "category": cat_acces, "price": "19.99", "stock": 40},
]

for data in products:
    Product.objects.get_or_create(
        name=data['name'],
        defaults={
            'category': data['category'],
            'brand': brand,
            'price': Decimal(data['price']),
            'stock': data['stock'],
            'description': f"Producto de alta calidad: {data['name']}"
        }
    )

print(f"✅ Productos creados: {Product.objects.count()}")
exit()
```

### 7. Iniciar el Servidor

```bash
python manage.py runserver --settings=gotogym.settings_local
```

**Salida esperada:**
```
✅ Usando configuración LOCAL (SQLite)
📁 Base de datos: /ruta/a/db_local.sqlite3
Performing system checks...

System check identified no issues (0 silenced).
Django version 6.0.2, using settings 'gotogym.settings_local'
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```

### 8. Abrir en el Navegador

```
🌐 Página principal: http://localhost:8000/
🔐 Panel Admin: http://localhost:8000/admin/
```

---

## 🎯 Script de Inicio Rápido

El proyecto incluye un script que automatiza todo:

**Linux/Mac:**
```bash
cd GoToGtymPrime
./start.sh
```

**Windows (PowerShell):**
```powershell
cd GoToGtymPrime\gotogym
python manage.py migrate --settings=gotogym.settings_local
python manage.py runserver --settings=gotogym.settings_local
```

---

## 🔍 Verificar Instalación

### Comprobar Python y pip:
```bash
python --version   # Debe ser 3.10+
pip --version
```

### Comprobar base de datos:
```bash
cd gotogym
python manage.py shell --settings=gotogym.settings_local
>>> from accounts.models import User
>>> User.objects.count()
>>> exit()
```

### Ver logs del servidor:
```bash
# El servidor muestra logs en la consola en tiempo real
# Presiona Ctrl+C para detener
```

---

## 🛠️ Configuración Avanzada

### Usar MySQL en lugar de SQLite

1. **Editar `gotogym/settings_local.py`:**

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'gotogym_local',
        'USER': 'tu_usuario',
        'PASSWORD': 'tu_password',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
```

2. **Crear base de datos MySQL:**

```sql
CREATE DATABASE gotogym_local CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON gotogym_local.* TO 'tu_usuario'@'localhost';
```

3. **Migrar:**

```bash
python manage.py migrate --settings=gotogym.settings_local
```

### Variables de Entorno (Opcional)

Crea un archivo `.env` en la raíz del proyecto:

```bash
# Django
DJANGO_SECRET_KEY=tu-clave-secreta-aleatoria-muy-larga
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Base de datos (si usas MySQL)
MYSQL_DATABASE=gotogym_local
MYSQL_USER=tu_usuario
MYSQL_PASSWORD=tu_password
MYSQL_HOST=localhost
MYSQL_PORT=3306

# Integraciones (opcional para desarrollo)
MERCADOPAGO_ACCESS_TOKEN=tu_token
ALEGRA_EMAIL=tu_email
ALEGRA_TOKEN=tu_token
HUBSPOT_PRIVATE_TOKEN=tu_token
```

Luego instala python-decouple:
```bash
pip install python-decouple
```

---

## 📝 Archivos de Configuración

### `gotogym/settings.py`
Configuración principal del proyecto (apunta a MySQL Azure por defecto)

### `gotogym/settings_local.py` ⭐
Configuración para desarrollo local (usa SQLite, DEBUG=True)

### `gotogym/settings_test.py`
Configuración para ejecutar tests

---

## 🚨 Solución de Problemas

### Error: "No module named 'MySQLdb'"
```bash
pip install mysqlclient
# O en Windows:
pip install PyMySQL
```

### Error: "Port already in use"
```bash
# Detener procesos usando el puerto 8000
# Linux/Mac:
lsof -ti:8000 | xargs kill -9

# Windows:
netstat -ano | findstr :8000
taskkill /PID <numero_pid> /F
```

### Error 404 en /admin/
```bash
# Asegúrate de usar settings_local:
python manage.py runserver --settings=gotogym.settings_local

# Verifica que las URLs no tengan prefijo /es/:
http://localhost:8000/admin/  ✅
http://localhost:8000/es/admin/  ❌
```

### Base de datos bloqueada (SQLite)
```bash
# Detén el servidor (Ctrl+C)
# Reinicia
python manage.py runserver --settings=gotogym.settings_local
```

### Migraciones inconsistentes
```bash
# Resetear base de datos local:
cd gotogym
rm db_local.sqlite3
python manage.py migrate --settings=gotogym.settings_local
python manage.py createsuperuser --settings=gotogym.settings_local
```

---

## 🧪 Ejecutar Tests

```bash
cd gotogym

# Todos los tests
python manage.py test --settings=gotogym.settings_test

# Un app específica
python manage.py test accounts --settings=gotogym.settings_test

# Test de integración Alegra
cd ..
DJANGO_SETTINGS_MODULE=gotogym.settings_test \
python -m unittest integrations.alegra.tests.test_client -v
```

---

## 📱 URLs Importantes

Una vez que el servidor esté corriendo en `http://localhost:8000/`:

| URL | Descripción |
|-----|-------------|
| `/` | Página principal (auto-redirige según idioma) |
| `/admin/` | Panel de administración Django |
| `/accounts/login/` | Login de usuarios |
| `/accounts/register/` | Registro de nuevos usuarios |
| `/products/` | Catálogo de productos |
| `/carrito/` | Carrito de compras |
| `/tienda/` | Tienda online |
| `/blog/` | Blog |
| `/dashboard/` | Dashboard (requiere login) |
| `/configuracion-marca/` | Configuración de marca |
| `/crm/` | CRM / HubSpot integration |
| `/setlang/` | Cambiar idioma (es/en/pt) |

---

## 🌍 Soporte Multi-idioma

El proyecto soporta 3 idiomas:
- 🇪🇸 Español (por defecto)
- 🇬🇧 English
- 🇧🇷 Português

Para cambiar idioma, usa el selector en la interfaz o visita `/setlang/`

---

## 📦 Estructura del Proyecto

```
GoToGtymPrime/
├── gotogym/                    # Proyecto Django principal
│   ├── manage.py              # Comando principal Django
│   ├── db_local.sqlite3       # Base de datos local (se crea al migrar)
│   ├── gotogym/               # Configuración del proyecto
│   │   ├── settings.py        # Settings producción
│   │   ├── settings_local.py  # Settings desarrollo ⭐
│   │   ├── settings_test.py   # Settings para tests
│   │   └── urls.py            # Rutas principales
│   ├── accounts/              # App de usuarios
│   ├── products/              # App de productos
│   ├── carrito/               # App carrito de compras
│   ├── tienda/                # App tienda
│   ├── blog/                  # App blog
│   └── ... (otras apps)
├── integrations/              # Integraciones externas
│   ├── alegra/               # Contabilidad
│   ├── mercadopago/          # Pagos
│   └── hubspot/              # CRM
├── requirements.txt           # Dependencias Python
└── start.sh                   # Script de inicio rápido
```

---

## 🔎 Diagnóstico Técnico Actual (Marzo 2026)

Este diagnóstico resume el estado real del repositorio para evitar diferencias
entre documentación y código en ejecución.

### 1. Arquitectura realmente activa

- Monolito Django en `gotogym/` como núcleo principal.
- Renderizado web con Django Templates (SSR) y apps por dominio.
- Base de datos:
    - Desarrollo local: SQLite (`settings_local.py`).
    - Entornos conectados: MySQL (`settings.py`), orientado a Azure MySQL.
- Docker Compose actual levanta solo el servicio web (no incluye servicio de
    base de datos local en `docker-compose.yml`).

### 2. Servicios funcionales disponibles

- **accounts**: registro, login, logout, recuperación de contraseña,
    actualización de perfil.
- **products**: CRUD de categorías, productos y marcas para operación interna.
- **tienda**: catálogo público con filtros y detalle de producto.
- **carrito**: agregar, quitar, actualizar productos y checkout.
- **blog**: listado de posts publicados con búsqueda y paginación.
- **contabilidad**: consulta de clientes y facturas vía Alegra.
- **influencer**: activación de perfil, dashboard y simulación de compras
    referidas.
- **configuracion_marca**: administración de paleta/identidad de marca.
- **crm**: endpoint de salud (`/crm/healthz`) activo.

### 3. Integraciones externas

- **Mercado Pago**: checkout redirige al `init_point` de la preferencia.
- **Alegra**: clientes y facturas disponibles desde la app de contabilidad.
- **HubSpot**: cliente base existe, pero creación/sincronización completa aún
    está en estado parcial (stub).

### 4. Hallazgos técnicos relevantes

- El comando de `gunicorn` en Docker apunta a `gotogym.wsgi:application`, pero
    la estructura actual resuelve correctamente `gotogym.gotogym.wsgi`.
- Existe inconsistencia de variables para Alegra entre `ALEGRA_TOKEN` y
    `ALEGRA_API_TOKEN`.
- DRF/JWT está instalado y configurado, pero no hay una superficie de API REST
    pública consolidada en rutas del proyecto.
- La cobertura de pruebas es baja en apps Django (varios `tests.py` vacíos).

### 5. Recomendación de estabilización (prioridad alta)

1. Corregir módulo WSGI del Dockerfile para despliegue estable.
2. Unificar variables de entorno de Alegra y documentarlas en un solo formato.
3. Definir qué endpoints CRM/HubSpot deben quedar expuestos en producción.
4. Agregar smoke tests mínimos en CI antes del despliegue a Azure Web App.

---

## ✅ Checklist de Instalación

- [ ] Python 3.10+ instalado
- [ ] Repositorio clonado
- [ ] Entorno virtual creado y activado
- [ ] Dependencias instaladas (`pip install -r requirements.txt`)
- [ ] Migraciones aplicadas (`python manage.py migrate --settings=gotogym.settings_local`)
- [ ] Superusuario creado (`python manage.py createsuperuser --settings=gotogym.settings_local`)
- [ ] Servidor iniciado (`python manage.py runserver --settings=gotogym.settings_local`)
- [ ] Navegador abierto en `http://localhost:8000/`
- [ ] Login en admin exitoso (`http://localhost:8000/admin/`)

---

## 🎓 Próximos Pasos

1. Explora el panel de administración
2. Crea productos, categorías y marcas
3. Prueba el flujo de registro/login
4. Agrega productos al carrito
5. Revisa la documentación de cada app
6. Comienza a desarrollar nuevas funcionalidades

---

## 📚 Documentación Adicional

- [ANALISIS_ESTRUCTURA.md](ANALISIS_ESTRUCTURA.md) - Análisis completo del proyecto
- [CORRECCIONES.md](CORRECCIONES.md) - Historial de correcciones
- [GUIA_ACCESO.md](GUIA_ACCESO.md) - Guía de acceso y bases de datos
- [README.md](../README.md) - Información general del proyecto

---

## 🆘 Soporte

Si encuentras problemas:
1. Revisa la sección "Solución de Problemas" arriba
2. Ejecuta `./verificar_db.sh` para ver el estado del sistema
3. Revisa los logs del servidor en la consola
4. Consulta la documentación de Django: https://docs.djangoproject.com/

---

**¡Listo para desarrollar! 🚀**
