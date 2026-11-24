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

- `TEST_PARALLEL`: procesos de la suite. Por defecto 1 (en local y en el CI).
  Con más de uno hace falta `tblib` (ya está en `requirements-dev.txt`); ver "Pruebas en paralelo" abajo.
  En una máquina con poca CPU conviene dejarlo en 1.
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

## Dependencias y fusion automatica de Dependabot

`.github/dependabot.yml` agrupa las actualizaciones menores y de parche en un
solo PR semanal por ecosistema (pip y GitHub Actions). Los saltos mayores de
`django`, `redis`, `pillow`, `psycopg2-binary`, `cryptography`, `mercadopago` y
`gunicorn` no se proponen: se actualizan a mano. Los mayores del resto de
paquetes y de las Actions si se abren como PR propio y se revisan a mano.

`.github/workflows/dependabot-automerge.yml` fusiona (squash) los PR de
`dependabot[bot]` cuyas actualizaciones sean todas menores o de parche, y solo
cuando todos los checks del PR terminaron en verde, incluidos
`Validacion y suite completa` y `Pruebas contra PostgreSQL`. Si no hay checks,
alguno falla, se agota la espera (65 min) o el tipo de actualizacion no se puede
determinar, no fusiona nada y el PR queda para revision. Si se renombra uno de
esos dos jobs en `ci.yml`, hay que actualizar `CHECKS_OBLIGATORIOS` en el
workflow; mientras tanto no se fusiona (falla hacia el lado seguro).

Detalles de diseno:

- Usa `pull_request_target` (el `GITHUB_TOKEN` de `pull_request` es de solo
  lectura en los PR de Dependabot) y nunca hace checkout ni ejecuta codigo del
  PR. Permisos: `contents: write` y `pull-requests: write` para fusionar, y
  `checks: read` para leer el resultado de los checks.
- Fusiona con `--match-head-commit` (solo el commit cuyos checks se verificaron)
  y sin `--admin`: si la rama exige algo mas, la fusion se rechaza.
- Ignora PR cuya ultima modificacion no sea de Dependabot.

Lo que debe hacer el dueno del repositorio en la interfaz de GitHub (el workflow
no puede hacerlo):

1. Settings > Branches: proteger `main` y marcar como requeridos los checks del
   CI (`Validacion y suite completa`, `Pruebas contra PostgreSQL`). Sin esto,
   nada impide fusionar a mano un PR con checks en rojo; el workflow igual los
   verifica por su cuenta.
2. Settings > General > Pull Requests: dejar permitido "Squash merging". Activar
   "Allow auto-merge" no es necesario para este workflow (espera los checks el
   mismo y fusiona al terminar), pero si se prefiere el flujo nativo de GitHub
   (`gh pr merge --auto`), esa opcion y la proteccion de rama con checks
   requeridos son obligatorias.

Dos limitaciones a tener presentes:

- El workflow no se pudo ejecutar en local: la logica de decision (jq) y la
  sintaxis del script se validaron, pero el primer PR real de Dependabot es la
  prueba definitiva. Conviene vigilarlo la primera semana.
- Una fusion hecha con el `GITHUB_TOKEN` no dispara otros workflows (regla de
  GitHub), de modo que `main_gotogymweb.yml`, que despliega con `push` a `main`,
  no se ejecuta por estas fusiones. Los cambios quedan en `main` y se despliegan
  con el siguiente push o con un `workflow_dispatch` manual. Si se quiere que
  cada fusion despliegue sola, hay que usar un token de una GitHub App o un PAT
  en lugar del `GITHUB_TOKEN`, decision del dueno del repositorio.

## pip-audit

El job `Vulnerabilidades conocidas en dependencias` de `ci.yml` es informativo
(`continue-on-error`) y escribe el resultado en el resumen del job. No se hizo
bloqueante porque `pip-audit` no filtra por severidad: ni sus opciones ni su
salida la incluyen (solo permite ignorar un identificador con `--ignore-vuln`),
asi que bloquear significaria detener el despliegue por cualquier vulnerabilidad,
tambien las bajas y las que ningun parche corrige todavia.

## Pruebas en paralelo (`--parallel`)

Si una prueba falla en un worker de `--parallel` y `tblib` no esta instalado,
Django no puede enviar el traceback al proceso principal y la corrida termina
con `TypeError: cannot pickle 'traceback' object`, sin decir que prueba fallo.
Eso no es un defecto del paralelismo ni de Windows: se reproduce con una
prueba trivial que falla (`assertEqual(1, 2)`) y desaparece al instalar
`tblib`, que entonces muestra el fallo real. Con `tblib` instalado, las apps
del proyecto pasan con `--parallel 2` (cada app por separado y el conjunto en
dos mitades), en Windows (spawn) incluido. `tblib` está fijado en `requirements-dev.txt`, así que el entorno que crea
`run_backend_checks.sh` ya lo tiene; para correr `manage.py test` a mano:

```bash
pip install -r requirements-dev.txt
python manage.py test . --parallel 2 --settings=gotogym.settings_test
```

Si la corrida paralela falla, el error real aparece ya con el traceback; si
ocurre en una prueba que en serie pasa, buscar estado compartido entre procesos
(archivos en rutas fijas de `tempfile.gettempdir()`, el `MEDIA_ROOT` real, cache).
Ojo con editar archivos de prueba mientras corre una suite en paralelo: los
workers vuelven a importar los modulos desde disco y pueden no encontrar una
prueba que el proceso principal si descubrio (`AttributeError: ... has no
attribute 'test_...'`).

## Piso de cobertura

El job `backend` de `ci.yml` define `COVERAGE_FAIL_UNDER` (hoy 90) y
`run_backend_checks.sh` lo pasa a `coverage report --fail-under`. Se fijo con la
medicion completa en serie de la suite (2.435 pruebas, 93,8 % de las lineas de
las apps) menos 3 puntos de margen. Para subirlo:

1. Medir en una corrida completa: `COVERAGE_FAIL_UNDER= bash environments/backend/run_backend_checks.sh`
   (sin piso, el reporte final imprime el `TOTAL`), o a mano desde `gotogym/`:
   `coverage run --rcfile=../pyproject.toml manage.py test . --settings=gotogym.settings_test`,
   `coverage combine --rcfile=../pyproject.toml` y `coverage report --rcfile=../pyproject.toml`.
2. Cambiar el valor entero de `COVERAGE_FAIL_UNDER` en `ci.yml` a la parte
   entera de lo medido menos 2 o 3 puntos de margen, y subirlo en el mismo PR
   que sube la cobertura. Nunca bajarlo para que pase un PR: si cae, falta una
   prueba.
