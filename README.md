# GoToGtymPrime
GoToGym Prime es el servicio al Cliente de la Marca GoToGym Sportwear as a Service.

Este repositorio contiene un monolito Django (`gotogym/`), con un modulo
`gotogym/integrations/` para los proveedores externos (Mercado Pago,
Alegra, HubSpot).

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

### Producción (PostgreSQL, Azure App Service)

Producción no se levanta a mano con `runserver`: corre en Azure App Service,
detrás de gunicorn, desplegado por el workflow de GitHub Actions
(`.github/workflows/main_gotogymweb.yml`). La base de datos es PostgreSQL,
resuelta desde la variable de entorno `DATABASE_URL` (ver `gotogym/gotogym/settings.py`).
El comando de arranque real vive en la configuración del App Service
(Azure Portal); `environments/azure/startup.sh` documenta la version de
referencia versionada en el repo.

**📖 Guía completa:** Ver [docs/DESPLIEGUE_LOCAL.md](docs/DESPLIEGUE_LOCAL.md)

---

## 📋 Documentación

- **[docs/DESPLIEGUE_LOCAL.md](docs/DESPLIEGUE_LOCAL.md)** - Instrucciones detalladas de instalación local
- **[docs/GUIA_ACCESO.md](docs/GUIA_ACCESO.md)** - Guía de acceso y bases de datos

---

## 🏗️ Arquitectura

### Proyecto Principal: `gotogym/` (Django Monolito)

**Apps implementadas:**
- `accounts` - Gestión de usuarios y autenticación
- `products` - Catálogo de productos
- `inventory` - Inventario y stock
- `carrito` - Carrito de compras
- `tienda` - Tienda online (catálogo, PDP)
- `orders` - Checkout y pedidos
- `payments` - Pagos
- `shipping` - Cotización de envío
- `blog` - Sistema de blog
- `contabilidad` - Integración con Alegra
- `influencer` - Gestión de influencers y referidos
- `administracion` - Panel administrativo interno
- `analitica` - Analítica de producto sin PII

### Integraciones: `gotogym/integrations/`

- **Alegra** - API de contabilidad
- **MercadoPago** - Procesamiento de pagos
- **HubSpot** - CRM y gestión de contactos

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

# Todos los tests (esta es la suite que corre CI, ver
# environments/backend/run_backend_checks.sh)
python manage.py test . administracion --settings=gotogym.settings_test

# Test específico de integración (ya en gotogym/, integrations/ vive ahi)
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

- **Backend:** Django 5.2 + Django REST Framework
- **Base de datos:** PostgreSQL (producción, Azure) / SQLite (desarrollo y tests)
- **Frontend:** Django Templates + Tailwind (CSS compilado y versionado, sin build de Node en el despliegue)
- **Autenticación:** Sesiones de Django (sitio) + JWT vía `djangorestframework-simplejwt` (`accounts/api_views.py`)
- **Pagos:** Mercado Pago
- **Contabilidad:** Alegra API
- **CRM:** HubSpot

---

## 📁 Estructura

```
GoToGtymPrime/
├── gotogym/                 # Django principal
│   ├── accounts/           # Usuarios
│   ├── products/           # Productos
│   ├── carrito/            # Carrito
│   ├── tienda/             # Tienda
│   ├── integrations/       # Integraciones externas
│   │   ├── alegra/
│   │   ├── mercadopago/
│   │   └── hubspot/
│   └── ...                 # Otras apps
├── environments/           # Scripts de CI, despliegue y checks
├── design/                 # Fuentes tipográficas fuente
└── docs/                   # Documentación
```

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
