# GoToGtymPrime
GoToGym Prime es el servicio al Cliente de la Marca GoToGym Sportwear as a Service.

Este repositorio contiene un proyecto Django clásico (`gotogym`) y un nuevo
esqueleto modular en `go-to-gym-platform` con frontend Next.js y microservicios.

## 🚀 Inicio Rápido

### Desarrollo Local (SQLite)

```bash
cd gotogym
python manage.py migrate --settings=gotogym.settings_local
python manage.py createsuperuser --settings=gotogym.settings_local
python manage.py runserver --settings=gotogym.settings_local
```

Accede a:
- 🌐 Frontend: http://localhost:8000/
- 🔐 Admin: http://localhost:8000/admin/

### Producción (MySQL Azure)

```bash
cd gotogym
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

**📖 Guía completa:** Ver [docs/DESPLIEGUE_LOCAL.md](docs/DESPLIEGUE_LOCAL.md)

---

## 📋 Documentación

- **[docs/DESPLIEGUE_LOCAL.md](docs/DESPLIEGUE_LOCAL.md)** - Instrucciones detalladas de instalación local
- **[docs/GUIA_ACCESO.md](docs/GUIA_ACCESO.md)** - Guía de acceso y bases de datos
- **[docs/ANALISIS_ESTRUCTURA.md](docs/ANALISIS_ESTRUCTURA.md)** - Análisis completo del proyecto
- **[docs/CORRECCIONES.md](docs/CORRECCIONES.md)** - Historial de cambios y correcciones

---

## 🏗️ Arquitectura

### Proyecto Principal: `gotogym/` (Django Monolito)

**Apps implementadas:**
- `accounts` - Gestión de usuarios y autenticación
- `products` - Catálogo de productos
- `carrito` - Carrito de compras
- `tienda` - Tienda online
- `blog` - Sistema de blog
- `configuracion_marca` - Personalización de marca
- `contabilidad` - Integración con Alegra
- `influencer` - Gestión de influencers
- `crm` - Integración con HubSpot
- `metricas` - Dashboard de métricas

### Integraciones: `integrations/`

- **Alegra** - API de contabilidad
- **MercadoPago** - Procesamiento de pagos
- **HubSpot** - CRM y gestión de contactos

### Proyecto Futuro: `go-to-gym-platform/` (Microservicios)

- `wellness_monitor` - Microservicio de monitoreo de salud
- `core_api` - APIs modulares
- `frontend/webapp` - PWA con Next.js

---

## ⚙️ Configuración

### Microservicio Wellness Monitor (Opcional)

```bash
cd go-to-gym-platform/backend/services/wellness_monitor
python manage.py migrate
python manage.py runserver 0.0.0.0:8001
```

### Frontend Next.js PWA (Opcional)

```bash
cd go-to-gym-platform/frontend/webapp
npm install
npm run dev
```

---

## 🔐 Variables de Entorno

### HubSpot

Para que la señal de usuarios cree contactos automáticamente en HubSpot:

```bash
export HUBSPOT_PRIVATE_TOKEN="tu_token_privado"
```

## 💳 Pagos con Mercado Pago

La tienda utiliza [Mercado Pago](https://www.mercadopago.com/) para procesar
los pagos. Configura las siguientes variables de entorno:

```bash
export MERCADOPAGO_PUBLIC_KEY="<PUBLIC_KEY>"
export MERCADOPAGO_ACCESS_TOKEN="<ACCESS_TOKEN>"
export MERCADOPAGO_CLIENT_ID="<CLIENT_ID>"
export MERCADOPAGO_CLIENT_SECRET="<CLIENT_SECRET>"
```

Al finalizar la compra se creará una *preference* y el usuario será
redireccionado al flujo de pago de Mercado Pago.

## 📊 Contabilidad con Alegra

Para emitir facturas y registrar gastos se utiliza [Alegra](https://www.alegra.com/).
Define las siguientes variables de entorno:

```bash
export ALEGRA_EMAIL="<EMAIL_DE_CUENTA>"
export ALEGRA_TOKEN="<TOKEN_DE_API>"
```

---

## 🧪 Tests

```bash
cd gotogym

# Todos los tests
python manage.py test --settings=gotogym.settings_test

# Test específico de integración
cd ..
DJANGO_SETTINGS_MODULE=gotogym.settings_test \
python -m unittest integrations.alegra.tests.test_client -v
```

---

## 🌍 Soporte Multi-idioma

El proyecto soporta 3 idiomas:
- 🇪🇸 Español (por defecto)
- 🇬🇧 English
- 🇧🇷 Português

---

## 📦 Tecnologías

- **Backend:** Django 6.0.2 + Django REST Framework
- **Base de datos:** MySQL (producción) / SQLite (desarrollo)
- **Frontend:** Django Templates + Next.js (PWA)
- **Autenticación:** JWT
- **Pagos:** Mercado Pago
- **Contabilidad:** Alegra API
- **CRM:** HubSpot

---

## 📁 Estructura

```
GoToGtymPrime/
├── gotogym/                 # Django principal (ACTIVO)
│   ├── accounts/           # Usuarios
│   ├── products/           # Productos
│   ├── carrito/            # Carrito
│   ├── tienda/             # Tienda
│   └── ...                 # Otras apps
├── integrations/           # Integraciones externas
│   ├── alegra/
│   ├── mercadopago/
│   └── hubspot/
├── go-to-gym-platform/     # Modular (EN DESARROLLO)
│   ├── backend/
│   │   ├── services/
│   │   └── core_api/
│   └── frontend/
│       └── webapp/
└── docs/                   # Documentación
```

---

## ✅ Estado del Proyecto

| Componente | Estado | Descripción |
|------------|--------|-------------|
| Django Monolito | ✅ Activo | Proyecto principal funcionando |
| Integraciones | ✅ Activo | Alegra, MercadoPago |
| Microservicio wellness | 🔶 Desarrollo | Opcional |
| Frontend Next.js | 🔶 Esqueleto | En desarrollo |

---

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

---

## 📄 Licencia

Este proyecto es privado y propiedad de GoToGym SaaS.

---

## 📞 Contacto

Para más información, consulta la documentación en el directorio `docs/` o ejecuta el script de verificación:

```bash
./verificar_db.sh
```
