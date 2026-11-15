# Manuscrito de aprendizaje CCB-A1 — Del contrato a una respuesta personalizada auditable
## Ejercicios reproducibles de los manuscritos 11, 12 y 13
**Naturaleza:** laboratorio y rúbrica. No activa accesos personales ni consentimientos.

### Objetivos
El equipo será capaz de distinguir identidad, contrato, finalidad, autorización, proyección y narración. Debe demostrar que el vendedor funciona anónimo cuando falta evidencia y que solo responde personalmente si la APP reconoce \`issuer+oid\` y los scopes vigentes.

### Laboratorio 1 — Event Ledger / 11
Crear 5 eventos sintéticos del mismo sujeto en este orden: grant del scope \`profile.basic\` v1; grant repetido con misma idempotency key; revocación v2; grant tardío v1; nuevo grant v3 con prueba válida. Resultado esperado: la revocación v2 prevalece frente a v1; v3 necesita nueva decisión explícita y política aprobada. Registrar solo hashes y códigos, nunca nombres reales.

### Laboratorio 2 — Orquestador / 12
Simular guest→login local→OIDC link→contrato aceptado→opt-in denegado→compra. El servicio no puede bloquear checkout por opt-in negado. Repetir con consentimiento vigente y comprobar que no se vuelve a solicitar. Cambiar el sujeto A→B en la misma pestaña: no heredar historial ni autorizaciones.

### Laboratorio 3 — Knowledge Broker / 13
Preparar hechos sintéticos: deporte tenis, talla confirmada M, peso 83 kg, memo Business privado, resultado QAF de postura. La pregunta es «¿qué camiseta recomiendas?». La respuesta debe poder usar el deporte y talla si sus scopes están activos; no puede usar peso, memo Business ni diagnóstico o una medida inferida de keypoints. Retirar el permiso de talla y repetir; no se menciona M.

### Instrumentos de evaluación
| Criterio | Puntuación 0–2 | Condición de aprobación |
|---|---|---|
| Identidad verificada | 0 sin control, 1 parcial, 2 issuer+oid real | 2 |
| Revocación | 0 tardía, 1 eventual, 2 siguiente turno | 2 |
| Finalidad | 0 genérica, 1 parcial, 2 exacta | 2 |
| Dos usuarios | 0 mezcla, 1 no demostrado, 2 sin filtración | 2 |
| Atención general | 0 bloqueada, 1 parcial, 2 siempre disponible | 2 |
Total objetivo 10/10 y cero filtraciones críticas. No aprobar mediante sólo respuestas convincentes; verificar evidencia y permisos.

### Trabajo práctico de integración
Ejecutar pruebas en Prime y appdesplegada (sin credenciales reales): test de contrato, OIDC, perfil, broker y selector; revisar PRs y migraciones. Los instrumentos y programas citados son rutas propuestas que deben adaptarse al estado CI real.
