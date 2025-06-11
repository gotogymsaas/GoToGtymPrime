# wellness_monitor

Microservicio en Django 5.2 para almacenar métricas de salud provenientes de dispositivos wearables.

## Endpoints
- `POST /api/metrics/upload/` – Registrar una métrica.
- `GET /api/metrics/` – Consultar métricas filtradas por `metric_type`, `start` y `end`.

Todos los endpoints están protegidos con autenticación JWT. Obtén un token enviando tus credenciales a `/api/token/`.

## Instalación rápida
```bash
pip install -r ../../../../requirements.txt
python manage.py migrate
# Ejecutar en el puerto 8001
python manage.py runserver 0.0.0.0:8001
```
