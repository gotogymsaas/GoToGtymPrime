# GoToGym Prime

GoToGym Prime es el servicio al Cliente de la Marca GoToGym Sportwear as a Service.

Este repositorio contiene:
- Un proyecto Django principal (`gotogym`) - Plataforma de e-commerce y gestión
- Una nueva arquitectura modular (`go-to-gym-platform`) con microservicios y frontend Next.js
- Integraciones con servicios externos (Mercado Pago, Alegra, HubSpot)

## 🚀 Instalación y Configuración Local

### Prerrequisitos

- Python 3.11 o superior
- Node.js 16+ y npm (para el frontend Next.js)
- Git

### ⚡ Inicio Rápido (Solo Django Principal)

Si solo quieres probar la aplicación Django principal:

```powershell
# 1. Activar entorno virtual (desde el directorio raíz del proyecto)
venv\Scripts\activate

# 2. Navegar al proyecto Django (IMPORTANTE: debes estar en gotogym/)
cd gotogym

# 3. Verificar que estás en el directorio correcto (debe mostrar manage.py)
ls manage.py

# 4. Ejecutar servidor
python manage.py runserver 127.0.0.1:8000
```

Luego abre http://127.0.0.1:8000 en tu navegador.

**⚠️ IMPORTANTE**: El archivo `manage.py` está dentro del directorio `gotogym/`, NO en la raíz del proyecto.

### 📋 Instalación Completa

### Opción 1: Instalación Manual (Recomendada para desarrollo)

#### 1. Clonar el repositorio
```bash
git clone <url-del-repositorio>
cd GoToGtymPrime
```

#### 2. Configurar el entorno virtual de Python

**Para Windows PowerShell:**
```powershell
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
venv\Scripts\activate
```

**Para Linux/Mac:**
```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
source venv/bin/activate
```

**Verificación**: Después de activar el entorno virtual, deberías ver `(venv)` al inicio de tu línea de comandos.

#### 3. Instalar dependencias de Python
```bash
pip install -r requirements.txt
```

**Nota para Windows**: Si obtienes un error con `python-oqs`, es normal. Este paquete no está disponible para Python 3.10 en Windows, pero no es esencial para el funcionamiento básico del proyecto.

#### 4. Configurar la base de datos del proyecto principal
```powershell
# IMPORTANTE: Navegar al directorio del proyecto Django
cd gotogym

# Verificar que estás en el directorio correcto
ls manage.py

# Configurar la base de datos
python manage.py migrate
python manage.py collectstatic --noinput
```

#### 5. Crear un superusuario (opcional)
```powershell
python manage.py createsuperuser
```

#### 6. Ejecutar el servidor Django principal
```powershell
python manage.py runserver 127.0.0.1:8000
```

El proyecto estará disponible en: http://127.0.0.1:8000

**Nota**: Si ves el mensaje "Watching for file changes with StatReloader" y "Starting development server at http://127.0.0.1:8000/", el servidor está funcionando correctamente. Puedes abrir esa URL en tu navegador.

#### 7. Configurar y ejecutar el microservicio wellness_monitor (opcional)
```powershell
# En una nueva terminal PowerShell, desde la raíz del proyecto
# Primero activar el entorno virtual:
venv\Scripts\activate
# Luego navegar y ejecutar:
cd go-to-gym-platform\backend\services\wellness_monitor
python manage.py migrate
python manage.py runserver 127.0.0.1:8001
```

El microservicio estará disponible en: http://127.0.0.1:8001

#### 8. Configurar y ejecutar el frontend Next.js (opcional)
```powershell
# En una nueva terminal PowerShell, desde la raíz del proyecto
cd go-to-gym-platform\frontend\webapp
npm install
npm run dev
```

El frontend estará disponible en: http://localhost:3000

### Opción 2: Docker (Alternativa)

#### 1. Ejecutar con Docker Compose
```bash
docker-compose up --build
```

El proyecto estará disponible en: http://localhost:8000

## 🔧 Configuración de Variables de Entorno

### Variables Opcionales

Puedes crear un archivo `.env` en la raíz del proyecto con las siguientes variables:

```bash
# Django
DJANGO_SECRET_KEY=tu-clave-secreta-aqui
DEBUG=True

# Base de datos (opcional, por defecto usa SQLite)
MYSQL_DATABASE=gotogym_bd
MYSQL_USER=gotogym_user
MYSQL_PASSWORD=tu-password
MYSQL_HOST=localhost
MYSQL_PORT=3306

# Mercado Pago (para pagos)
MERCADOPAGO_PUBLIC_KEY=tu-public-key
MERCADOPAGO_ACCESS_TOKEN=tu-access-token
MERCADOPAGO_CLIENT_ID=tu-client-id
MERCADOPAGO_CLIENT_SECRET=tu-client-secret

# Alegra (para contabilidad)
ALEGRA_EMAIL=tu-email@ejemplo.com
ALEGRA_TOKEN=tu-token-de-api

# HubSpot (para CRM)
HUBSPOT_PRIVATE_TOKEN=tu-token-privado
```

## 📁 Estructura del Proyecto

```
GoToGtymPrime/
├── gotogym/                    # Proyecto Django principal
│   ├── accounts/              # Gestión de usuarios
│   ├── products/              # Catálogo de productos
│   ├── carrito/               # Carrito de compras
│   ├── tienda/                # Funcionalidad de tienda
│   ├── contabilidad/          # Integración con Alegra
│   ├── crm/                   # Integración con HubSpot
│   ├── influencer/            # Sistema de influencers
│   └── manage.py              # Comando Django
├── go-to-gym-platform/        # Nueva arquitectura modular
│   ├── backend/services/      # Microservicios
│   └── frontend/webapp/       # Aplicación Next.js PWA
├── integrations/              # Clientes para APIs externas
├── docker-compose.yml         # Configuración Docker
└── requirements.txt           # Dependencias Python
```

## 🌟 Funcionalidades Principales

### Proyecto Django Principal (Puerto 8000)
- **E-commerce**: Catálogo de productos, carrito de compras, checkout
- **Gestión de usuarios**: Registro, login, perfiles
- **Sistema de influencers**: Comisiones y referencias
- **Integración de pagos**: Mercado Pago
- **Contabilidad**: Integración con Alegra
- **CRM**: Integración con HubSpot
- **Multiidioma**: Español, Inglés, Portugués

### Microservicio Wellness Monitor (Puerto 8001)
- Monitoreo de métricas de bienestar
- API REST para datos de salud

### Frontend Next.js PWA (Puerto 3000)
- Aplicación web progresiva
- Interfaz moderna y responsive
- Consulta de métricas del microservicio

## 🔗 URLs Principales

- **Aplicación principal**: http://localhost:8000
- **Admin Django**: http://localhost:8000/admin
- **API REST**: http://localhost:8000/api/
- **Wellness Monitor**: http://localhost:8001
- **Frontend PWA**: http://localhost:3000

## 🛠️ Comandos Útiles

```bash
# Crear migraciones
python gotogym/manage.py makemigrations

# Aplicar migraciones
python gotogym/manage.py migrate

# Crear superusuario
python gotogym/manage.py createsuperuser

# Recopilar archivos estáticos
python gotogym/manage.py collectstatic

# Ejecutar tests
python gotogym/manage.py test

# Cargar datos de ejemplo (si existen fixtures)
python gotogym/manage.py loaddata nombre_fixture
```

## 🐛 Solución de Problemas

### Error: "No module named 'django'"
- Asegúrate de haber activado el entorno virtual: `venv\Scripts\activate`
- Verifica que veas `(venv)` al inicio de tu línea de comandos
- Instala las dependencias: `pip install -r requirements.txt`

### Error: "can't open file 'manage.py'" o "No such file or directory"
**Causa**: Estás ejecutando comandos de Django desde el directorio incorrecto.

**Solución**:
```powershell
# 1. Asegúrate de estar en el directorio raíz del proyecto
pwd  # Debe mostrar: C:\...\GoToGtymPrime

# 2. Navega al directorio correcto
cd gotogym

# 3. Verifica que manage.py existe
ls manage.py  # Debe mostrar el archivo

# 4. Ahora ejecuta los comandos Django
python manage.py runserver 127.0.0.1:8000
```

**Estructura correcta**:
```
GoToGtymPrime/          ← Directorio raíz (aquí activas venv)
├── gotogym/            ← Aquí ejecutas comandos Django
│   ├── manage.py       ← Este archivo debe existir
│   └── ...
└── venv/               ← Entorno virtual
```

### Error de base de datos
- Ejecuta las migraciones desde el directorio `gotogym`: `python manage.py migrate`

### Puerto ocupado
- Cambia el puerto: `python manage.py runserver 127.0.0.1:8080`
- O detén otros procesos de Python: `Get-Process | Where-Object {$_.ProcessName -eq "python"} | Stop-Process -Force`

### Problemas con archivos estáticos
- Ejecuta desde el directorio `gotogym`: `python manage.py collectstatic --noinput`

### Error con PowerShell y el operador `&&`
- PowerShell no soporta `&&`. Ejecuta los comandos por separado:
  ```powershell
  cd gotogym
  python manage.py migrate
  ```

### El servidor no responde
- Verifica que veas el mensaje: "Starting development server at http://127.0.0.1:8000/"
- Abre http://127.0.0.1:8000 en tu navegador
- Si usas un firewall, asegúrate de permitir conexiones en el puerto 8000

## 📝 Desarrollo

Para contribuir al proyecto:

1. Crea una rama para tu feature: `git checkout -b feature/nueva-funcionalidad`
2. Realiza tus cambios
3. Ejecuta los tests: `python gotogym/manage.py test`
4. Haz commit de tus cambios: `git commit -m "Descripción del cambio"`
5. Sube tu rama: `git push origin feature/nueva-funcionalidad`
6. Crea un Pull Request

## 📄 Licencia

Este proyecto es privado y pertenece a GoToGym.