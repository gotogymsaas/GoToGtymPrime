# Despliegue y operación de GoToGym Prime

Verificado contra Azure y el código el 14 de octubre de 2026. Para ejecutar el proyecto en tu equipo, ver `docs/GUIA_ACCESO.md`. La bitácora de marzo de 2026 que había en este lugar (`DESPLIEGUE_LOCAL.md`) quedó en el historial de git.

## Producción hoy

| Qué | Valor |
|---|---|
| Aplicación | App Service Linux `gotogym-prime`, grupo `rg-gotogym-prime`, Python 3.12, Always On |
| Dirección pública | `https://shop.gotogym.store` (y `gotogym-prime.azurewebsites.net`) |
| Base de datos | PostgreSQL, por la variable `DATABASE_URL` |
| Respaldos | El servidor flexible `psql-gotogym-prod` (grupo `rg-gotogym-data`) conserva respaldos automáticos 7 días, sin redundancia geográfica |
| Slots | No hay slot de staging: cada despliegue va directo a producción |
| HTTPS | `httpsOnly` está apagado en la aplicación; la redirección la hace Django con `SECURE_SSL_REDIRECT` |

## Cómo se despliega

1. Un push a `main` (o ejecutar el workflow a mano) lanza `.github/workflows/main_gotogymweb.yml`.
2. El job `build` valida: ruff, import-linter, mypy, `manage.py check`, pruebas con cobertura, gobernanza de diseño y smoke del frontend.
3. El job `deploy` empaqueta y publica por Kudu (`zipdeploy`) y comprueba que el sitio responda.
4. El **Startup Command** que ejecuta el App Service (configurado en el Portal, no en git) es:

   ```
   python gotogym/manage.py migrate --noinput && python gotogym/manage.py collectstatic --noinput && gunicorn --chdir gotogym gotogym.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120 --access-logfile '-' --error-logfile '-'
   ```

   El `migrate` es el del proyecto: adapta una base antigua del programa "influencer" y crea la tabla de caché (`django_cache`) si la caché vive en la base. `wsgi.py` no migra.
5. `environments/azure/startup.sh` es una versión de referencia del mismo arranque que además carga el Journal (`seed_journal --solo-faltantes`). Producción **no** la usa; si hace falta cargar entradas del Journal, ejecutar ese comando por SSH.

## Variables de entorno

Las lee `gotogym/gotogym/settings.py`. Con `DEBUG` apagado y sin `DJANGO_SECRET_KEY` la aplicación no arranca.

| Variable | Para qué | Estado en producción |
|---|---|---|
| `DJANGO_SECRET_KEY`, `DEBUG`, `DATABASE_URL` | Núcleo | Declaradas |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Dominios permitidos | Declaradas (`shop.gotogym.store` y el de Azure) |
| `SECURE_PROXY_SSL_HEADER`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT` | HTTPS | Declaradas; `SECURE_SSL_REDIRECT` estaba en `false` |
| `SECURE_HSTS_SECONDS` | HSTS. Arranca en 3600 en producción; subir por etapas a 604800 y luego 31536000 | Sin declarar (usa 3600) |
| `SITIO_URL` | Dirección pública para los enlaces de los correos. Por defecto `https://gotogym.store` | **Falta: debe ser `https://shop.gotogym.store`** |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | Correo real. Sin `EMAIL_HOST` los correos salen por consola | Faltan |
| `PAYMENT_PROVIDER`, `MERCADOPAGO_ACCESS_TOKEN`, `MERCADOPAGO_WEBHOOK_SECRET`, `PAYMENTS_MOCK_UI_ENABLED` | Pagos. Por defecto `mock` | Faltan |
| `ALEGRA_EMAIL`, `ALEGRA_API_TOKEN` | Contabilidad | Faltan |
| `SENTRY_DSN`, `SENTRY_ENVIRONMENT` | Monitoreo de errores | Faltan |
| `REDIS_URL` | Caché compartida en Redis. Sin ella y con `DATABASE_URL`, la caché es una tabla de la base | Opcional |
| `ADMIN_URL` | Ruta del administrador de Django (por defecto `admin/`); conviene una no obvia, por ejemplo `gestion-xxxx/` | Sin declarar |
| `TRUSTED_PROXY_HOPS` | Proxies de confianza delante de la aplicación (1 en producción) para obtener la IP real del cliente | Sin declarar (usa 1) |
| `RATE_LIMIT_ENABLED` | Límite de intentos de acceso y de uso (por defecto activo) | Sin declarar |
| `ORDER_PAYMENT_WINDOW_HOURS` | Horas antes de cancelar un pedido sin pagar (48) | Sin declarar |
| `RECURSOS_AFILIADOS_ROOT` | Carpeta del material de marca de afiliados | Sin declarar |

Plantilla completa: `environments/azure/.env.release.example`.

## Tareas periódicas

No hay un programador desplegado. Cada una se ejecuta también al abrir la pantalla que la necesita, pero conviene programarlas (WebJob de Azure o una tarea programada):

| Comando | Cada cuánto | Qué hace |
|---|---|---|
| `python manage.py cancelar_pedidos_vencidos` | Cada hora | Cancela pedidos sin pagar pasado el plazo y devuelve sus cupones |
| `python manage.py confirmar_comisiones` | A diario | Confirma comisiones de afiliados cuyo periodo de validación terminó |
| `python manage.py aplicar_bajas` | A diario | Aplica las bajas de afiliados con preaviso vencido |

## Respaldos, restauración y reversión

- **Base de datos.** Restauración a un punto en el tiempo de los últimos 7 días: crea un servidor nuevo, no pisa el actual (`az postgres flexible-server restore --resource-group rg-gotogym-data --name <servidor-nuevo> --source-server psql-gotogym-prod --restore-time <fecha-hora-UTC>`). Conviene ensayarla antes de abrir al público y valorar subir la retención.
- **Código.** Para volver a una versión anterior, ejecutar el workflow sobre el commit anterior o revertir el commit en `main`. Sin slot de staging no hay intercambio instantáneo.
- **Archivos subidos.** Las imágenes que se suban desde el panel quedan en `gotogym/media/` dentro de la aplicación desplegada; verificar que ese almacenamiento persista entre despliegues (pendiente de resolver).

## Antes de abrir al público

1. `SITIO_URL`, `EMAIL_*`, `SENTRY_DSN` y, para cobrar, `PAYMENT_PROVIDER=mercadopago` con sus credenciales y el webhook registrado.
2. `SECURE_SSL_REDIRECT=true` (o `httpsOnly` en Azure) y comprobar que todo el sitio funciona por HTTPS antes de subir HSTS.
3. `PAYMENTS_MOCK_UI_ENABLED` apagado.
4. `python manage.py security_checklist` en el App Service.
5. Revisar que no exista el administrador heredado con una contraseña publicada: `python manage.py revisar_claves_heredadas`.
6. Catálogo, precios y existencias reales (`python manage.py audit_catalog`).
