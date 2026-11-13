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
4. Anotar cualquier hallazgo operativo en `docs/DESPLIEGUE.md`.

Atajo (todo en uno):

```bash
bash environments/run_all_checks.sh
```

## 3) Azure preflight (Fase 2)

Archivo:

- `environments/azure/run_fase2_preflight.sh`

Uso:

```bash
bash environments/azure/run_fase2_preflight.sh
```

Variables opcionales:

- `AZURE_SUBSCRIPTION_ID`
- `AZURE_RELEASE_RESOURCE_GROUP`
- `AZURE_RELEASE_WEBAPP`

## 4) Azure apply (Fase 2)

Archivos:

- `environments/azure/.env.release.example`
- `environments/azure/apply_fase2_config.sh`

## Suite de pruebas del backend

`run_backend_checks.sh` es lo mismo que ejecuta el CI (`.github/workflows/ci.yml`)
en cada pull request y antes de cada despliegue. Corre, en orden: ruff,
import-linter, mypy, `manage.py check`, migraciones pendientes
(`makemigrations --check`), `check --deploy` con la configuración de producción
simulada y la suite completa con cobertura:

```bash
bash environments/backend/run_backend_checks.sh
```

Variables útiles:

- `TEST_PARALLEL`: procesos de la suite. Por defecto 2 en local y uno por núcleo
  cuando `CI=true`. En una máquina con poca CPU conviene dejarlo bajo.
- `COVERAGE_FAIL_UNDER`: piso de cobertura. Si no se define, el reporte no falla.
  Se fija con el valor medido en una corrida completa del CI y solo se sube
  cuando sube la cobertura.

El CI ejecuta además un segundo job contra PostgreSQL 16 con las apps que mueven
dinero e inventario (`orders`, `payments`, `inventory`, `afiliados`) y el
limitador de tasa. SQLite ignora `select_for_update`, de modo que las pruebas de
concurrencia (`test_concurrencia.py` en `orders` y `payments`, y las de última
unidad de inventario) solo se ejercitan allí. Para repetirlo en local hace falta
un PostgreSQL desechable y las variables `POSTGRES_*`:

```bash
cd gotogym
python manage.py test orders payments inventory afiliados \
  --settings=gotogym.settings_test_postgres
```

Uso seguro (dry-run por defecto):

```bash
cp environments/azure/.env.release.example environments/azure/.env.release
bash environments/azure/apply_fase2_config.sh
```

Ejecucion real (solo cuando la suscripcion este Enabled):

```bash
DRY_RUN=false bash environments/azure/apply_fase2_config.sh
```

## Validacion antes de subir (hooks de git)

Para que un build roto no llegue al historial de GitHub, el repositorio trae
hooks versionados en `.githooks/` que corren la misma validacion que el job
`build` del CI. Se activan una vez por clon:

```bash
bash environments/install_git_hooks.sh
```

- `pre-commit`: ruff y gobernanza de diseno (~1 s).
- `pre-push`: ruff, mypy, `manage.py check`, migraciones pendientes y la suite
  de pruebas con `settings_test` (~2 min).

Tambien se puede correr a mano con
`bash environments/backend/validate_local.sh` (o con `--quick`). Requiere
`ruff` y `mypy` en el entorno (`pip install -r requirements-dev.txt`). Si
hace falta saltarla de forma puntual: `git commit --no-verify` o
`git push --no-verify`; el CI sigue siendo la barrera final.
