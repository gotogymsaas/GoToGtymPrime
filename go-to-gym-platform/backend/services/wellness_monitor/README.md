# wellness_monitor

Microservicio en Django 5.2 para almacenar métricas de salud provenientes de dispositivos wearables.

## Endpoints
- `POST /api/metrics/upload/` – Registrar una métrica.
- `GET /api/metrics/` – Consultar métricas filtradas por `metric_type`, `start` y `end`.

Todos los endpoints están protegidos con autenticación JWT.

## Páginas HTML
- `/api/` muestra una página simple de comprobación.
- `/api/metrics/page/` lista las métricas del usuario autenticado.

## Instalación rápida
```bash
# instala las dependencias principales si no cuentas con un `requirements.txt`
pip install django djangorestframework djangorestframework-simplejwt django-cors-headers psycopg2-binary

# o bien, si ya tienes un archivo de requerimientos disponible
# pip install -r ../../../../requirements.txt

python manage.py migrate
```
