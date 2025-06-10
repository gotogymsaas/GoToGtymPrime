# wellness_monitor

Microservicio en Django 5.2 para almacenar métricas de salud provenientes de dispositivos wearables.

## Endpoints
- `POST /api/metrics/upload/` – Registrar una métrica.
- `GET /api/metrics/` – Consultar métricas filtradas por `metric_type`, `start` y `end`.

Todos los endpoints están protegidos con autenticación JWT.

## Instalación rápida
```bash
pip install django djangorestframework djangorestframework-simplejwt django-cors-headers psycopg2-binary
python manage.py migrate
```
