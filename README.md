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
