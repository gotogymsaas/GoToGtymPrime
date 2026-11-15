# Manuscrito de aprendizaje CCB-A2: privacidad, seguridad y evaluación científica
## Manual de entrenamiento de los manuscritos 14, 15 y 16
**Fecha:** noviembre 2026 · **Uso:** formación de operadores técnicos y equipo de privacidad. No modifica sistemas.

### Objetivos
- Explicar qué significa revocación en el siguiente turno y demostrarlo con trazas sin PII.
- Identificar la diferencia entre identidad humana y credencial de servicio.
- Auditar una respuesta del vendedor separando afirmaciones con evidencia, afirmaciones sin fundamento y datos no autorizados.
- Diseñar un experimento que no convierta la selección de usuarios con permiso en una inferencia causal.

### Práctica A: derechos del titular
Caso de usuario sintético con \`tailoring.measurements\` activo, talla orientativa y memo comercial. Al revocar el scope en Prime se borran los datos sujetos a la finalidad y se invalida el epoch. El siguiente turno debe no mencionar medidas ni talla derivada de ellas. Registrar evidencia de autorización y comprobación de borrado, no datos reales. Simular restauración de backup y demostrar que el evento de revocación sigue prevaleciendo.

### Práctica B: amenazas
Ataques sintéticos: inyección del tipo «ignora instrucciones» dentro de una descripción de camiseta, payload de identidad con oid de B, jti repetido, Key Vault sin resolver, campo nuevo \`health.weight\` en context. Deben ser denegados o retirados sin afectar catálogo general. La regla de aprobación requiere 0 leaks.

### Práctica C: evaluación QAF
Construir 24 recorridos: 8 anónimos, 8 con perfil y 8 con perfil + experiencias permitidas. Etiquetar verdad canónica de nombre, deporte, disponibilidad del producto y estado de medidas. Comparar C, I y η. Toda diferencia reportada debe llevar N y error estándar/intervalo de confianza. No se permite afirmar mejora con muestras ficticias.

### Rúbrica de aprobación
| Dominio | Evaluación |
|---|---|
| Derechos del titular | Revocación comprobada al siguiente turno |
| Seguridad | 0 falsos privilegios y 0 filtraciones |
| Evidencia | 100% de claims personales tienen fuente válida |
| Investigación | No se confunde correlación con causalidad |
| Producto | Checkout disponible sin personalización |
Cada objetivo es obligatorio; un incidente de privacidad invalida el ensayo.

### Trabajo de cierre
Revisar \`commerce_agent/identity.py\`, \`context_broker.py\`, \`turn.py\`, los modelos de consentimiento Prime y los manifiestos legales. Entregar una matriz de amenazas y un plan de rollback con pruebas, aprobados por roles técnicos y legales.
