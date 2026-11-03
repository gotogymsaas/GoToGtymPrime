# QAF-Cyber SHADOW — GoToGtymPrime

Estado: **PREPARADO, NO ACTIVADO NI VALIDADO EN AZURE**. Sólo observación de seguridad.

## Contrato y arquitectura
Project ID exacto: `GoToGtymPrime`. Fuente revisada: `gotogymsaas/cybersecurity@03900cf91f81ccb001fffaefa079ebd13e50ad18`.
Commit limpio → cinco scanners → SHA-256 → Blob privado → adaptadores canónicos → SecurityEvent v1 → Gateway.
Collector comprueba remote allowlisted, checkout limpio, HEAD completo de 40 caracteres antes/después y reportes fuera del árbol.
El hash de configuración se calcula sobre JSON ordenado del perfil de cada herramienta.
SecurityEvent usa `tool_name`, `rule_id`, `evidence_ref.report_sha256` y `evidence_ref.json_pointer`.
El Gateway devuelve `trace_id` en el recibo; no es campo de entrada del evento v1.

## Inventario revisado
Snapshot: `8dc271d879905a0f42a1b20052ba2f78bd964f1e`. No se reemplazan workflows existentes.
- `.github/workflows/main_gotogymweb.yml`
- `Dockerfile`
- `package-lock.json`
- `package.json`
- `requirements.txt`

Python/Django y JavaScript/HTML/CSS. Se conservan despliegues y lógica funcional.

## Cinco fuentes y perfil
Semgrep SAST (auto detecta lenguajes); OSV dependencias; Gitleaks secretos con --redact; Trivy vulnerabilidades/misconfiguración; Syft inventario CycloneDX.
Un paquete Syft no se transforma por sí solo en vulnerabilidad.
Los comandos exactos están en scanner-profile.json y sólo los ejecuta la allowlist central, nunca el LLM.
Versiones, hashes stdout de --version y referencias de reglas/feeds quedan null hasta medir el runner real.
Configuración y comandos del perfil son declarativos: el tooling fija los comandos y no admite shell del perfil.
El validador compara la configuración declarada con la revisada y bloquea perfiles incompletos antes del job OIDC.

## Configuración pendiente y ejecución
1. Revisar y fusionar este PR sólo con checks verdes.
2. Crear/proteger Environment `qaf-shadow`, restringido a main y con revisión del operador.
3. Configurar identidad Azure EXCLUSIVA de GoToGtymPrime; issuer https://token.actions.githubusercontent.com, audience api://AzureADTokenExchange, subject `repo:gotogymsaas/GoToGtymPrime:environment:qaf-shadow`.
4. Variables del environment: QAF_EMITTER_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID, QAF_KEY_VAULT_NAME, QAF_EVIDENCE_ACCOUNT, QAF_GATEWAY_ORIGIN. No se inventaron valores.
5. Secret GitHub QAF_TOOLING_READ_TOKEN: lectura contents del tooling privado exclusivamente. Como el caller lo pasa explícitamente, configurarlo en repository/organization secrets restringido a este repo. Permitir uso del reusable privado desde este repo.
6. Runner efímero aislado [self-hosted, qaf-scanners], Azure CLI/Python y cinco binarios revisados; acceso privado a Blob/Key Vault/Gateway y egress a feeds autorizado.
7. Capturar bytes stdout de cada [tool, --version] sin normalizar y SHA-256; registrar versión y feed/reglas realmente observados. Completar null mediante PR; status OPERATOR_REVIEWED sólo tras revisión.
8. Ejecutar `python3 .github/qaf/validate.py --operational`. El perfil pendiente aborta antes del job con OIDC.
9. Ejecutar manualmente QAF Cyber SHADOW seleccionando main. Sin schedule ni push de scanners inicialmente.
10. Revisar receipt restringido del runner: project_id, report_hashes, accepted, traces y duplicate. Un lote de cero hallazgos no prueba aceptación de eventos. Reemitir para demostrar idempotencia.

## Permisos y privacidad
GitHub contents:read; id-token:write sólo en emisor. Sin push/merge/deploy/administración/secrets write.
Azure: leer únicamente secret `qaf-ingest-GoToGtymPrime`; Blob create/read exclusivamente en `evidence-restricted/GoToGtymPrime/`, sin overwrite/delete/list transversal. El emisor necesita read para revalidar hash.
No asignar Contributor/Owner ni roles Blob genéricos a nivel cuenta/contenedor que permitan cruces: usar RBAC condicionado y comprobarlo.
Sin acceso de emisor a BD/Service Bus ni modificación de recursos.
Reportes potencialmente sensibles salen sólo al Blob restringido; eventos minimizados van al Gateway. No se envía el repo completo al Gateway, secretos a logs/LLM, ni crudos a Actions artifacts.
Retención y eliminación segura del runner son responsabilidad operacional. Gitleaks redacta; otros scanners pueden incluir rutas o fragmentos. Nunca entregar crudos al LLM.

## Gates operativos y límites
Probar identidad propia ALLOW y todas las otras project IDs DENY en Gateway, Blob y Key Vault. Tests locales no sustituyen RBAC real.
El tooling revisado usa Semgrep auto y feeds dinámicos: no demuestra reproducibilidad científica con reglas/feeds congelados. La mejora debe hacerse centralmente y repinear SHA.
No se verificó runner, Azure, roles, environment ni Gateway.
El reusable usa checkout del evento y collector comprueba estabilidad. Las pruebas locales validan configuración/contratos, no un scan actual.
Dependencias runtime instaladas por tooling y políticas de red/retención requieren revisión del operador.
No declarar SHADOW_VALIDATED hasta recibir evidencia actual y demostrar aislamiento real.

## Revisar, detener y rollback
Validación local: `python3 -m pip install PyYAML==6.0.3`; `python3 -m unittest discover -s tests/qaf_shadow -v`.
Los tests verifican scope, SHA, allowlist, permisos, triggers, bloqueo de perfil incompleto y ausencia de publicación de crudos en el nuevo workflow. La detección de literales de credenciales está acotada a archivos nuevos; no es auditoría de secretos históricos.
Detener: deshabilitar QAF Cyber SHADOW en Actions, cancelar run activo y destruir runner; revocar federación/ingest token del proyecto si procede.
Rollback: revertir commit de integración, preservando evidencia/auditoría conforme retención. No cambia lógica de la aplicación.

