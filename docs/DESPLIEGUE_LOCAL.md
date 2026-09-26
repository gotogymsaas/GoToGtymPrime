# 🚀 Guía de Despliegue Local - GoToGymPrime

> **Nota (agregada al revisar la estructura del repo):** la seccion que
> sigue ("Checklist Maestro de Ejecucion") es la bitacora **cerrada** de un
> proceso de despliegue de marzo 2026 -- se lee de abajo hacia arriba en
> importancia: termina confirmando `gotogym-prime` / `rg-gotogym-prime`
> como el entorno definitivo, que es el que sigue en uso hoy. Las "Reglas
> operativas activas" (punto 2, "commit + push en cada respuesta") **no
> son la forma de trabajar actual** y no deben seguirse como instruccion
> vigente. Todo lo fechado "Marzo 2026" en este documento, incluido el
> "Diagnostico Tecnico" mas abajo, es una foto de ese momento, no el
> estado de hoy -- en particular, `configuracion_marca` y `crm` que ahi se
> listan como servicios activos no estan registrados en `INSTALLED_APPS`
> actualmente. La guia de instalacion que sigue despues de la bitacora
> si esta vigente.

## 🧭 Checklist Maestro de Ejecución (Azure) — bitácora histórica, ver nota arriba

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

#### 2026-03-18 — Continuidad de implementación (iteración actual)

- Calidad de build:
    - se agregan tests mínimos de humo en `gotogym/accounts/tests.py` para evitar pipeline con `NO TESTS RAN`.
    - cobertura mínima validada sobre rutas críticas: home, login y healthz CRM.
    - resultado validado: `Found 3 test(s)` y `OK` en `environments/backend/run_backend_checks.sh`.
- Fase 2 operativa:
    - se agrega `environments/azure/.env.release.example` como plantilla de configuración de release.
    - se agrega `environments/azure/apply_fase2_config.sh` para:
        - crear slot staging (si no existe),
        - configurar startup command,
        - aplicar app settings críticas,
        - habilitar logging básico de App Service.
    - el script trabaja en `DRY_RUN=true` por defecto para ejecución segura.
    - ejecución actual: bloqueada por estado de suscripción `Warned`.
        - salida: `habilita la suscripción antes de aplicar configuración Fase 2`.
- Operación local de pruebas:
    - se agrega `environments/run_all_checks.sh` para ejecutar backend + frontend en una sola corrida.
    - resultado de la corrida integrada:
        - backend: `manage.py check` sin issues y suite con `Found 3 test(s)` / `OK`.
        - frontend smoke: respuestas `HTTP 302` esperadas en `/`, `/accounts/login/`, `/tienda/`, `/products/products/`, `/blog/`.
        - cierre: `[all-checks] Backend + frontend validados correctamente.`

#### 2026-03-26 — Plan de ajuste de despliegue (actualizado)

- Resultado de verificación en entorno Azure actual (CLI local):
    - suscripción visible: `Azure subscription 1` (tenant `ed18f421-bdd4-4536-ac49-cc48eb76e01f`).
    - resource groups visibles: `rg-gotogym-app`, `rg-gotogym-data`, `rg-gotogym-ai`, `rg-gotogym-observability`, entre otros.
    - Web App visible para despliegue: `app-gotogym-api-green-pnvfv3` en `rg-gotogym-app`.
    - no se encontraron en este contexto los recursos `gotogymweb` / `gotogymweb` definidos originalmente.
- Implicación operativa:
    - F2/F3 siguen bloqueadas por desalineación entre recursos objetivo documentados y recursos reales del tenant activo.

### Plan de implementación propuesto (F2 -> F4)

1. Alinear objetivo de release al entorno Azure activo
    - Confirmar si el release final será sobre:
        - opción A: recuperar acceso a suscripción/recurso `gotogymweb` original, o
        - opción B: mover release al Web App `app-gotogym-api-green-pnvfv3` en `rg-gotogym-app`.
    - Criterio de cierre: suscripción, RG y Web App definitivos aprobados en esta bitácora.

2. Ajustar parámetros de infraestructura en scripts Fase 2
    - Actualizar defaults o variables de entorno en:
        - `environments/azure/run_fase2_preflight.sh`
        - `environments/azure/apply_fase2_config.sh`
    - Variables mínimas: `AZURE_SUBSCRIPTION_ID`, `AZURE_RELEASE_RESOURCE_GROUP`, `AZURE_RELEASE_WEBAPP`, `AZURE_RELEASE_SLOT`.
    - Criterio de cierre: preflight apunta al recurso correcto y responde sin `ResourceGroupNotFound`.

3. Completar configuración de App Settings para arranque real
    - Críticas ya contempladas en scripts:
        - `DJANGO_SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `MERCADOPAGO_ACCESS_TOKEN`, `ALEGRA_API_TOKEN`.
    - Faltantes de base de datos para producción (según `settings.py`):
        - `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, `MYSQL_PORT`.
    - Criterio de cierre: app settings completas y sin secretos hardcodeados.

4. Validar permisos OIDC del workflow de GitHub Actions
    - Revisar que la identidad de `azure/login@v2` tenga permisos efectivos sobre RG/Web App objetivo.
    - Criterio de cierre: paso "Preflight Azure deployment access" exitoso en GitHub Actions.

5. Ejecutar secuencia operativa de despliegue
    - `bash environments/run_all_checks.sh` (validación local integrada).
    - `bash environments/azure/run_fase2_preflight.sh` (preflight infraestructura).
    - `DRY_RUN=true bash environments/azure/apply_fase2_config.sh` (simulación segura).
    - `DRY_RUN=false bash environments/azure/apply_fase2_config.sh` (aplicación real).
    - Lanzar workflow de deploy y validar salud funcional.
    - Criterio de cierre: despliegue verde y verificaciones de login/catálogo/checkout correctas.

6. Cerrar fases y rollback
    - Cerrar F2 cuando infraestructura/settings/logs estén listos.
    - Cerrar F3 cuando pipeline complete build+deploy en verde.
    - Ejecutar F4 validando smoke productivo.
    - Documentar plan de rollback de F5 (slot swap inverso o redeploy de artefacto previo).

#### 2026-03-26 — Implementación Opción B (entorno Azure activo)

- Cambios aplicados para alinear despliegue al entorno activo:
    - `environments/azure/.env.release.example` actualizado con:
        - `AZURE_SUBSCRIPTION_ID=c6015f72-55d5-4282-ba0b-f02152d798f7`
        - `AZURE_RELEASE_RESOURCE_GROUP=rg-gotogym-app`
        - `AZURE_RELEASE_WEBAPP=app-gotogym-api-green-pnvfv3`
        - host de `ALLOWED_HOSTS/CORS_ALLOWED_ORIGINS` al dominio real del Web App.
        - incorporación de variables MySQL (`MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, `MYSQL_PORT`).
    - `environments/azure/run_fase2_preflight.sh`:
        - defaults de suscripción/RG/WebApp actualizados al entorno activo.
        - validación de app settings extendida para incluir variables MySQL.
    - `environments/azure/apply_fase2_config.sh`:
        - defaults de suscripción/RG/WebApp actualizados al entorno activo.
        - variables requeridas extendidas para incluir MySQL.
        - aplicación de app settings MySQL en `az webapp config appsettings set`.
    - workflow `.github/workflows/main_gotogymweb.yml`:
        - parametrización con `AZURE_WEBAPP_NAME` y `AZURE_RESOURCE_GROUP`.
        - preflight y deploy ajustados al Web App real.

- Validación ejecutada posterior a cambios:
    - `bash environments/azure/run_fase2_preflight.sh` ✅
        - Web App objetivo encontrado y en estado `Running`.
        - startup actual detectado en App Service.
        - hallazgos pendientes: slot `staging` inexistente y app settings faltantes (`MERCADOPAGO_ACCESS_TOKEN`, `ALEGRA_API_TOKEN`, variables MySQL).
    - `DRY_RUN=true bash environments/azure/apply_fase2_config.sh` ✅ (guardrail)
        - falla controlada por variables faltantes en `.env.release` (comportamiento esperado de seguridad).

- Próximo paso operativo inmediato:
    - crear `environments/azure/.env.release` desde la plantilla y completar secretos reales.
    - reintentar `DRY_RUN=true` y luego `DRY_RUN=false` para cerrar Fase 2.

#### 2026-03-26 — Retarget operativo final a gotogym-prime

- Ajuste de objetivo confirmado en operación:
    - Web App objetivo: `gotogym-prime`
    - Resource Group: `rg-gotogym-prime`
    - Host esperado: `gotogym-prime.azurewebsites.net`
- Alineación aplicada en scripts/plantilla:
    - `environments/azure/.env.release.example`
    - `environments/azure/run_fase2_preflight.sh`
    - `environments/azure/apply_fase2_config.sh`
- Estado actual:
    - Web App `gotogym-prime` validado en `Running`.
    - pendiente completar secretos reales para ejecutar `apply_fase2_config.sh` en modo real (`DRY_RUN=false`).

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
python manage.py seed_catalog --settings=gotogym.settings_local
```

Siembra el catálogo base (categorías, marcas y productos) de forma
idempotente — correrlo de nuevo actualiza en vez de duplicar. Usa
`--dry-run` para ver qué haría sin escribir nada. (El snippet que antes
vivía aquí pegaba código directo en `manage.py shell` usando un campo
`price` que ya no existe en `Product` — se llama `base_price` — y por eso
fallaba si alguien lo copiaba tal cual.)

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
Django version 5.2, using settings 'gotogym.settings_local'
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
Configuración principal del proyecto (PostgreSQL vía `DATABASE_URL` en
producción; hay un camino heredado a MySQL para entornos viejos que
todavía lo declaren, pero no es el que usa `gotogym-prime` hoy)

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

# Test de integración Alegra (integrations/ vive dentro de gotogym/, no
# hace falta salir de esta carpeta)
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
│   ├── integrations/          # Integraciones externas
│   │   ├── alegra/           # Contabilidad
│   │   ├── mercadopago/      # Pagos
│   │   └── hubspot/          # CRM
│   └── ... (otras apps)
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
    - Producción (`gotogym-prime`): PostgreSQL vía `DATABASE_URL`
      (`settings.py`). Nota agregada despues de este diagnostico: en
      Marzo 2026 el entorno activo todavia era MySQL/Azure; para cuando
      se retoma este documento ya habia migrado a Postgres.
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
