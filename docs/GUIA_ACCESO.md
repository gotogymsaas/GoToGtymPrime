# Guía de acceso: cómo ejecutar el proyecto y entrar a cada panel

Vigente al 2 de octubre de 2026.

## Ejecutarlo en tu equipo

### En Windows: un solo paso

Ejecuta `EJECUTAR_LOCAL.bat` en la raíz del repositorio. Crea el entorno virtual si falta, instala las dependencias, aplica las migraciones, carga las entradas del Journal que falten y levanta el servidor en `http://localhost:8000/` (o en el 8001 si el 8000 está ocupado).

### Manual (cualquier sistema)

```bash
python -m venv .venv
source .venv/bin/activate          # En Windows: .venv\Scripts\activate
pip install -r requirements.txt

cd gotogym
python manage.py migrate --settings=gotogym.settings_local
python manage.py seed_journal --solo-faltantes --settings=gotogym.settings_local
python manage.py createsuperuser --settings=gotogym.settings_local
python manage.py runserver --settings=gotogym.settings_local
```

También sirve `./start.sh`, que hace lo mismo y pregunta antes de aplicar migraciones o crear el superusuario.

## A dónde entrar

Todas las rutas llevan prefijo de idioma; en español es `/es/`.

| Qué | URL local |
|---|---|
| Portada y tienda | `http://localhost:8000/es/` y `/es/tienda/` |
| Panel interno (ventas, analítica, productos, pedidos, cupones, usuarios, afiliados) | `/es/admin-panel/` |
| Analítica de comportamiento | `/es/admin-panel/analitica/` |
| Administración de Django | `/es/admin/` |
| Contabilidad (Alegra) | `/es/contabilidad/clientes/` |
| Panel de afiliados | `/es/influencer/dashboard/` |
| Comprobación de salud | `/healthz` |

El panel interno exige una cuenta con `is_staff`; la administración de Django, un superusuario.

## Cuentas

El proyecto **no documenta credenciales**. Crea tu propio superusuario con `createsuperuser` (arriba) y úsalo para entrar a los paneles. Para probar el flujo de un cliente, regístrate desde `/es/accounts/register/`.

## Bases de datos

| Entorno | Base | Cómo se elige |
|---|---|---|
| Desarrollo | SQLite, archivo `gotogym/db_local.sqlite3` | `--settings=gotogym.settings_local` |
| Pruebas | SQLite en memoria | `--settings=gotogym.settings_test` |
| Producción | PostgreSQL | Variable `DATABASE_URL` con la configuración por defecto |

Los archivos `*.sqlite3` no se versionan. El soporte para MySQL (variables `MYSQL_*`) es heredado y no se usa en entornos nuevos.

### Revisar qué hay en tu base local

```bash
bash verificar_db.sh
```

o, desde `gotogym/`:

```bash
python manage.py audit_catalog --settings=gotogym.settings_local        # catálogo e inventario
python manage.py security_checklist --settings=gotogym.settings_local   # variables sensibles
python manage.py shell --settings=gotogym.settings_local
```

## Pruebas

```bash
cd gotogym
python manage.py test                                   # suite completa de las apps
python manage.py test . administracion --settings=gotogym.settings_test   # igual que el CI
```

## Antes de subir cambios

Activa la validación local una sola vez por clon:

```bash
bash environments/install_git_hooks.sh
```

Desde entonces cada commit pasa por el lint y cada push por la validación completa (lint, tipos, migraciones pendientes y pruebas), la misma que el pipeline de GitHub. Detalles en `environments/README.md`.

## Problemas frecuentes

- **El puerto 8000 está ocupado**: el `.bat` usa el 8001 solo; en manual, `python manage.py runserver 8001 --settings=gotogym.settings_local`.
- **Una página dice que falta un archivo estático**: ejecuta con `--settings=gotogym.settings_local` (la configuración de producción espera `collectstatic`).
- **Faltan las entradas del Journal**: `python manage.py seed_journal --solo-faltantes --settings=gotogym.settings_local`.
- **Cambié un modelo**: `python manage.py makemigrations` y luego `migrate`; el pre-push avisa si falta una migración.
