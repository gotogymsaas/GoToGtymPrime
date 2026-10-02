# Registro histórico: primeras correcciones del proyecto (febrero de 2026)

> Este archivo es un **registro histórico**. Describe los problemas que se corrigieron para que el proyecto arrancara por primera vez y ya no refleja el estado actual. Para la estructura vigente ver `ANALISIS_ESTRUCTURA.md`; para ejecutarlo, `GUIA_ACCESO.md`.

## Problemas corregidos entonces

1. **Configuración desalineada.** `ROOT_URLCONF` y `WSGI_APPLICATION` apuntaban a un módulo que no existía en el monolito (`wellness_monitor`) y `INSTALLED_APPS` incluía una app inexistente (`monitor`). Se corrigieron para apuntar a `gotogym.*`.
2. **Modelo de usuario personalizado sin declarar.** Django usaba `auth.User` y `accounts.User` a la vez. Se agregó `AUTH_USER_MODEL = 'accounts.User'`.
3. **Conflicto de fusión sin resolver en `README.md`** (marcadores de git). Se limpió el archivo.
4. **Dependencia de MySQL faltante.** Se instaló entonces un conector de MySQL. Hoy la base de producción es PostgreSQL y MySQL es solo un camino heredado.
5. **Internacionalización mal configurada.** Las rutas usaban `i18n_patterns` sin idiomas declarados y `LANGUAGE_CODE` estaba en `en-us`. Se fijó el español como idioma por defecto y se agregó `LocaleMiddleware` y `LANGUAGES`.

## Qué cambió desde entonces

- Apps que se mencionaban y ya no existen: `configuracion_marca`, `crm` y `metricas`. El panel de métricas hoy vive dentro de `administracion`.
- El proyecto modular `go-to-gym-platform/` (microservicio y PWA) que se describía como futuro **no está en el repositorio**.
- La integración con HubSpot sigue siendo un esqueleto.
- Las pruebas pasaron de archivos vacíos a una suite completa con validación automática antes de subir cambios.
