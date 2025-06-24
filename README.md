<<<<<<< HEAD
# gotogym
=======
# GoToGtymPrime
GoToGym Prime es el servicio al Cliente de la Marca GoToGym Sportwear as a Service.

Este repositorio contiene un proyecto Django clásico (`gotogym`) y un nuevo
esqueleto modular en `go-to-gym-platform` con frontend Next.js y microservicios.

Para pruebas locales puedes iniciar el microservicio `wellness_monitor` en el
puerto `8001` y el proyecto Django principal en `8000`:

```bash
python go-to-gym-platform/backend/services/wellness_monitor/manage.py migrate
python go-to-gym-platform/backend/services/wellness_monitor/manage.py runserver 0.0.0.0:8001

python gotogym/manage.py migrate
python gotogym/manage.py runserver 0.0.0.0:8000
```

La aplicación PWA se encuentra en `go-to-gym-platform/frontend/webapp` y puede
consultar las métricas del microservicio.

Para que la señal de usuarios cree contactos automáticamente en HubSpot debes
definir la variable de entorno `HUBSPOT_PRIVATE_TOKEN` con tu token privado.

## Pagos con Mercado Pago

La tienda utiliza [Mercado Pago](https://www.mercadopago.com/) para procesar
los pagos. Configura las siguientes variables de entorno con tus credenciales
de producción:

```bash
export MERCADOPAGO_PUBLIC_KEY="<PUBLIC_KEY>"
export MERCADOPAGO_ACCESS_TOKEN="<ACCESS_TOKEN>"
export MERCADOPAGO_CLIENT_ID="<CLIENT_ID>"
export MERCADOPAGO_CLIENT_SECRET="<CLIENT_SECRET>"
```

Al finalizar la compra se creará una *preference* y el usuario será
redireccionado al flujo de pago de Mercado Pago.

## Contabilidad con Alegra

Para emitir facturas y registrar gastos se utiliza [Alegra](https://www.alegra.com/).
Define las siguientes variables de entorno con tus credenciales de API:

```bash
export ALEGRA_EMAIL="<EMAIL_DE_CUENTA>"
export ALEGRA_TOKEN="<TOKEN_DE_API>"
```
>>>>>>> 0e6e1bad419e6ab057c6fb7929bf260f07e3bd01
