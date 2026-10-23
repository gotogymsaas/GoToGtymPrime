# GoToGtymPrime
GoToGym Prime es el servicio al Cliente de la Marca GoToGym Sportwear as a Service.

Este repositorio contiene un monolito Django (`gotogym/`), con un modulo
`gotogym/integrations/` para los proveedores externos (Mercado Pago,
Alegra).

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
(Azure Portal) y es: `python gotogym/manage.py migrate --noinput && python gotogym/manage.py
collectstatic --noinput && gunicorn --chdir gotogym gotogym.wsgi:application --bind 0.0.0.0:8000
--workers 2 --timeout 120`. Las migraciones se aplican ahí, una vez por arranque; `wsgi.py` no migra.
`environments/azure/startup.sh` es una versión de referencia que además carga el Journal.

**📖 Guía completa:** Ver [docs/DESPLIEGUE.md](docs/DESPLIEGUE.md)

---

## 📋 Documentación

- **[docs/DESPLIEGUE.md](docs/DESPLIEGUE.md)** - Producción, variables de entorno, tareas periódicas y respaldos
- **[docs/GUIA_ACCESO.md](docs/GUIA_ACCESO.md)** - Cómo ejecutar el proyecto y entrar a cada panel
- **[docs/ANALISIS_ESTRUCTURA.md](docs/ANALISIS_ESTRUCTURA.md)** - Estructura, rutas, flujo de compra y configuración

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
- `afiliados` - Gestión de afiliados y referidos
- `administracion` - Panel administrativo interno
- `analitica` - Analítica de producto sin PII

### Integraciones: `gotogym/integrations/`

- **Alegra** - API de contabilidad
- **MercadoPago** - Procesamiento de pagos

---

## 🔐 Variables de Entorno

### Correo, pagos y monitoreo

`EMAIL_HOST` (con sus variables `EMAIL_*`), `PAYMENT_PROVIDER` (`mock` por defecto),
`MERCADOPAGO_ACCESS_TOKEN`, `MERCADOPAGO_WEBHOOK_SECRET` y `SENTRY_DSN` activan,
respectivamente, el envío real de correo, el proveedor de pago real y el monitoreo de
errores. `SITIO_URL` fija la dirección pública que llevan los enlaces de los correos. La
lista completa está en `docs/DESPLIEGUE.md`.

## 💳 Pagos con Mercado Pago

Por defecto la tienda usa un proveedor de pago **simulado**. El proveedor real de
[Mercado Pago](https://www.mercadopago.com/) está construido (preferencias, webhook con
verificación de firma y reembolsos), pero **todavía no se probó con credenciales reales**.
Para activarlo en un entorno:

```bash
export PAYMENT_PROVIDER="mercadopago"
export MERCADOPAGO_ACCESS_TOKEN="<ACCESS_TOKEN>"
export MERCADOPAGO_WEBHOOK_SECRET="<SECRETO_DEL_WEBHOOK>"
```

Registra `/pagos/webhook/mercadopago/` como URL de notificaciones en Mercado Pago y
asegúrate de que `PAYMENTS_MOCK_UI_ENABLED` quede apagado fuera de desarrollo.

## 📊 Contabilidad con Alegra

Para emitir facturas y registrar gastos se utiliza [Alegra](https://www.alegra.com/).
Define las siguientes variables de entorno:

```bash
export ALEGRA_EMAIL="<EMAIL_DE_CUENTA>"
export ALEGRA_TOKEN="<TOKEN_DE_API>"
```

---

## 🧪 Pruebas y validación

```bash
cd gotogym

python manage.py test                       # suite completa

# Igual que el pipeline (ver environments/backend/run_backend_checks.sh)
python manage.py test . administracion --settings=gotogym.settings_test
```

Antes de subir cambios, activa la validación local una sola vez por clon:

```bash
bash environments/install_git_hooks.sh
```

Cada commit pasa por el lint y cada push por la misma validación del pipeline (lint,
tipos, migraciones pendientes y pruebas). Detalles en
[environments/README.md](environments/README.md).

---

## 🌍 Soporte Multi-idioma

El proyecto soporta 3 idiomas:
- 🇪🇸 Español (por defecto)
- 🇬🇧 English
- 🇧🇷 Português (catálogo parcial, sin selector)

Con el selector en inglés, todo el sitio de cara al cliente sale en inglés: tienda, carrito, checkout, cuenta, área de afiliados, Journal, políticas, términos y correos. Los correos del pedido salen en el idioma en que se hizo la compra (`Order.language`).

**Cómo agregar o cambiar un texto**
1. Envuélvelo: `{% trans "..." %}` / `{% blocktrans %}` en plantillas; `gettext` / `gettext_lazy` en Python (no uses `_`, a veces es una variable descartable).
2. Agrega su traducción en `gotogym/locale/en/LC_MESSAGES/django.po` y recompila `django.mo` (`python manage.py compilemessages`, o con `polib` si no tienes gettext, como en Windows).
3. Los textos largos (políticas, términos, Journal) viven en módulos o plantillas por idioma: `politicas_contenido_en.py`, `terms_and_conditions_en.html`, `afiliados/terminos_en.html`, `blog/journal_en.py`.
4. El contenido que viene de la base de datos (nombre y descripción de productos, categorías, colores, tallas) se traduce con el filtro `traducir`, que usa el `.po` como diccionario: un producto nuevo se ve en español hasta que su nombre se agregue al catálogo.

`gotogym/test_ingles_completo.py` recorre las páginas de `/en/` y falla si encuentra texto en español.

---

## 📦 Tecnologías

- **Backend:** Django 5.2 + Django REST Framework
- **Base de datos:** PostgreSQL (producción, Azure) / SQLite (desarrollo y tests)
- **Frontend:** Django Templates + Tailwind (CSS compilado y versionado, sin build de Node en el despliegue)
- **Autenticación:** Sesiones de Django, con reglas de contraseña y límite de intentos de acceso
- **Pagos:** Mercado Pago (proveedor real construido, apagado por defecto)
- **Contabilidad:** Alegra API

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
