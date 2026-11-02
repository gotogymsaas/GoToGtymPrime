# Evidencia de validación - 2026-11-02

## Resultados locales

| Área | Prueba ejecutada | Resultado |
|---|---|---|
| Núcleo Django | manage_tests.py test tests | 43 aprobadas |
| Prime | manage.py test accounts | 128 aprobadas después de aislar el caché de RegistroTests |
| Developers backend | npm test -- --runInBand | 42 aprobadas; 2 PostgreSQL omitidas localmente por falta de servidor |
| Developers frontend | npm test -- --runInBand | 18 aprobadas, incluidas 5 de identidad |
| Coach bridge | django test universal_identity, settings aislados | 12 aprobadas |
| Coach schema | makemigrations --check --dry-run, settings aislados | Sin cambios pendientes |
| Developers build | tsc y vite build | Construcciones correctas; Vite advierte bundle >500 KB |
| Coach login JS | node --check para cuatro scripts inline | Sintaxis correcta |
| Prime controles de calidad | ruff, mypy, import-linter | Sin fallos: 300 fuentes tipadas y 2 contratos de dependencias conservados |
| Prime suite esencial de despliegue | 224 casos, settings_test, incluye accounts.test_oidc | 221 aprobados y 3 omitidos por la suite existente |
| PDFs | Render de las 12 páginas y revisión visual | Cuatro PDFs legibles de tres páginas |

Los cinco conjuntos de identidad, cuentas y frontend suman 243 pruebas aprobadas; dos casos PostgreSQL no se ejecutaron localmente. Además se ejecutó la suite esencial de Prime (224 casos: 221 aprobados y 3 omitidos), que comparte casos con accounts; no sumar ambos como pruebas únicas ni sumar reejecuciones o línea base.

## Línea base de Prime

Se ejecutó accounts en un worktree limpio de 8dc271d879905a0f42a1b20052ba2f78bd964f1e: 108 pruebas, dos fallos por HTTP 429 en accounts.test_contrasenas. Los mismos fallos aparecieron en el árbol nuevo antes del ajuste. La corrección limpia el caché antes/después de RegistroTests; no relaja el rate limit del producto. La suite de integración OIDC añade 20 casos. No se ejecutó la suite completa histórica del repositorio ni se reutiliza como resultado el número 1478 del README anterior.

## Qué prueban los dobles de prueba

El núcleo verifica firmas y claims con claves RSA propias, discovery/JWKS simulados y sesiones Django de prueba. Developers usa fetch simulado y un repositorio en memoria sólo con NODE_ENV=test. Coach usa auth.User y un generador de payload sustituido para probar el puente; no carga toda la arquitectura de api.User ni verifica en esa suite UserSerializer/_build_post_login_context reales. Cada alcance queda separado.

## Validación de PostgreSQL preparada en CI

backend/tests/identity.postgres.test.ts de Developers contiene dos pruebas de ocho consumos concurrentes con una sola respuesta exitosa. El workflow identity-tests configura PostgreSQL 16. Hasta observar esa ejecución no se declara ensayo real de concurrencia superado. La migración SQL y el repositorio se incluyen, pero no se aplicaron a una base del usuario.

## Controles que aún requieren evidencia externa

- Crear/configurar Entra y verificar iss/oid/aud reales; user flow con correo verificado y MFA según política.
- Ejecutar migraciones en staging, comprobar permisos y TLS de PostgreSQL y configurar caché compartido para límites de vinculación en Django si hay varios workers.
- Probar login/callback/return en navegador y PWA, conservación de carrito, términos y destinos del Coach con modelos reales.
- Entrar a las tres aplicaciones con la misma identidad y verificar que sus roles y datos no se trasladan.
- Definir revocación global y step-up de 2FA local. El SSO no invalida por sí mismo los JWT emitidos en otras apps.
- Revisar CI y PR antes de integración. Esta evidencia local no equivale a despliegue Azure.

## Evidencia adicional observada en GitHub Actions

Developers ejecutó PostgreSQL 16 real y aprobó los 44 casos del backend, incluidos los dos de consumo concurrente (ocho intentos y un solo éxito). Ejecución: https://github.com/gotogymsaas/gotogymdevelopers/actions/runs/41499164682 . El frontend también se construyó correctamente. Esto valida concurrencia en el entorno CI, no en Azure ni con Entra.

Los workflows del núcleo y del puente del Coach también completaron ejecuciones satisfactorias. Consultar los checks del último commit en cada PR para el estado más reciente.
