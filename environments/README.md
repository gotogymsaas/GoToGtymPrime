# Entornos de Pruebas

Este repositorio usa un monolito Django donde el frontend actual se entrega por
plantillas HTML (SSR). Por eso, el entorno de pruebas se separa en:

- `backend`: validaciones y pruebas Django.
- `frontend`: smoke tests HTTP sobre rutas de UI.

## 1) Backend

Archivos:

- `environments/backend/.env.test.example`
- `environments/backend/run_backend_checks.sh`

Uso:

```bash
cp environments/backend/.env.test.example environments/backend/.env.test
bash environments/backend/run_backend_checks.sh
```

## 2) Frontend (templates Django)

Archivos:

- `environments/frontend/.env.test.example`
- `environments/frontend/run_frontend_smoke.sh`

Uso (con backend levantado):

```bash
cp environments/frontend/.env.test.example environments/frontend/.env.test
bash environments/frontend/run_frontend_smoke.sh
```

## Flujo recomendado para pasar a pruebas

1. Ejecutar checks backend.
2. Levantar app local (`python manage.py runserver --settings=gotogym.settings_local`).
3. Ejecutar smoke frontend.
4. Registrar resultados en `docs/DESPLIEGUE_LOCAL.md`.
