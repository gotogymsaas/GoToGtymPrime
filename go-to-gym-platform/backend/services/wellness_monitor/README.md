# wellness_monitor

Microservicio en Django 5.2 para almacenar métricas de salud provenientes de dispositivos wearables.

## Endpoints
- `POST /api/metrics/upload/` – Registrar una métrica.
- `GET /api/metrics/` – Consultar métricas filtradas por `metric_type`, `start` y `end`.

hijjd8-codex/desarrollar-microservicio-wellness_monitor-en-django
Todos los endpoints están protegidos con autenticación JWT.

## Páginas HTML
- `/api/` muestra una página simple de comprobación.
- `/api/metrics/page/` lista las métricas del usuario autenticado.

## Instalación rápida
```bash
# instala las dependencias principales si no cuentas con un `requirements.txt`
pip install django djangorestframework djangorestframework-simplejwt django-cors-headers psycopg2-binary

# o bien, si ya tienes un archivo de requerimientos disponible
# pip install -r ../../../requirements.txt

python manage.py migrate
```

## Estado de integraciones con wearables
| Marca / Ecosistema | Estado sugerido | Método de integración |
| ------------------ | --------------- | -------------------- |
| Google Fit | ✅ Integrar ahora | REST API + OAuth2 |
| Apple Health | ✅ Integrar ahora | HealthKit (iOS native) |
| Samsung Health | ✅ Integrar ahora | Samsung Health SDK |
| Fitbit | 🔜 En fase 2 | REST API + OAuth2 |
| Garmin | 🔜 En fase 2 | Requiere aprobación |
| Huawei Health | ⛔ Omitir por ahora | SDK cerrado |

Todos los endpoints están protegidos con autenticación JWT. Obtén un token enviando tus credenciales a `/api/token/`.

## Instalación rápida
```bash
pip install -r ../../../../requirements.txt
python manage.py migrate
# Ejecutar en el puerto 8001
python manage.py runserver 0.0.0.0:8001
```
 main
