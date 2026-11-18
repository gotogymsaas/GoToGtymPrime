# QAF Cognitive Commerce Bridge — Programa integral de implementación y aprendizaje
**GoToGym / 14-11-2026.** Serie adicional a los manuscritos 06–10. Investigación de ingeniería, no declaración de despliegue E2E ni aprobación legal.

## Estructura: tres manuscritos de investigación → uno de aprendizaje

| Fase | Manuscritos | Documento de aprendizaje | Objetivo |
|---|---|---|---|
| 1: autorizaciones y contexto | 11 Ledger de decisiones; 12 BPMN onboarding; 13 Broker de memoria | Aprendizaje A1 | Identidad y finalidad verificadas, atención sin autorizaciones repetidas |
| 2: privacidad y operación | 14 Derechos y revocación; 15 Zero Trust; 16 Evaluación QAF | Aprendizaje A2 | Seguridad y prueba de experiencia sin acceso indebido |
| 3: experiencias y fit | 17 Postura/arquitectura; 18 Alta Costura Inteligente; 19 Aceptación E2E | Aprendizaje A3 | Derivación voluntaria a APP y pruebas de usuarios |

## Precisión de los documentos
- Los manuscritos 17 y 18 explican por qué la pose 2D de Exp-006/012/013 **no es una medida en centímetros ni un diagnóstico**. El ajuste requiere medidas voluntarias, recientes y guía de tallas o incertidumbre explícita.
- En Prime, el scope opt-in "experiences.commerce_guidance" es una implementación de un PR independiente, desactivada por defecto; no comparte resultados.
- El vínculo de issuer+oid verificado y la firma de servicio son independientes del consentimiento comercial.
- Los manuscritos 09–10 están sujetos a aprobación jurídica en PR separado; no se activan términos o permisos retroactivos.
- Las fórmulas QAF son hipótesis de ingeniería; no demostración de aceleración cuántica.

## Entregables técnicos por repositorio
**Django/appdesplegada:** futura Decision API después de aprobación jurídica; Context Broker para el estado de completitud de experiencias; selector de evidencia, CTA y pruebas entre usuarios.
**Prime/Shop:** consentimiento individual, medidas confirmadas con cinta, CTA a la APP, migración aditiva, continuidad de chat y prueba de compra sin opt-in.

## Estado comprobable, diferenciando documentos de producto
- Documentación QAF 06–08 publicada; 09–10 en PR de revisión jurídica.
- Manuscritos 11–19 y A1–A3 en este PR documental.
- Implementación parcial de 17–18 en PR de Prime y Django: permiso, estado de completitud y sugerencias con límites.
- Pendiente: Ledger interoperable real, Decision API, tablas por producto para fitting premium y aceptación humana en producción con cuenta autorizada.

## Gate end-to-end
1. CI y revisión jurídica/seguridad según el cambio.
2. SHA servido de ambos App Services y migraciones aplicadas.
3. Cuenta registrada en ambos con issuer+oid verificados.
4. Consentimiento vigente; revocación efectiva antes del turno siguiente.
5. No exportar resultados de las experiencias corporales al vendedor.
6. Pruebas A/B contra mezcla entre usuarios.
7. Compra operativa sin permisos opcionales, y acta humana de P01–P24.

## Referencias
ISO 8559-1:2017, confirmada en 2026: https://www.iso.org/standard/61686.html
Google MediaPipe Pose Landmarker: https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker
NIST AI RMF: https://www.nist.gov/itl/ai-risk-management-framework
