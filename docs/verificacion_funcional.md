# Verificación Funcional Pendiente

A continuación se listan los aspectos que requieren revisión o implementación para cubrir los criterios solicitados.

- [ ] **PWA / Web App**
  - Verificar carga correcta en desktop y móvil.
  - Validar navegación como invitado sin restricciones.
  - Confirmar funcionamiento offline completo y disponibilidad de `service-worker`.
  - Integrar registro de FCM (`registerFCM`) en el flujo de login para notificaciones push.
  - Revisar elementos SEO básicos (metadatos y rutas amigables).

- [ ] **Autenticación**
  - Validar registro y login básicos.
  - Reemplazar `make_password` por un algoritmo de cifrado post‑cuántico (`python-oqs` o `pqcrypto`).
  - Confirmar que el token de recuperación de contraseña expire a las 24 horas.

- [ ] **Chat IA**
  - Mostrar el botón de chat solo al iniciar sesión.
  - Integrar orquestador (LangChain o n8n) para respuestas básicas.
  - Guardar historial por usuario en base de datos.

- [ ] **Planes y Pagos**
  - Implementar selección de plan y pago con MercadoPago.
  - Activar el plan vía webhook tras pago exitoso.
  - Sincronizar datos del cliente con HubSpot y Alegra.

- [ ] **E‑commerce**
  - Mostrar productos sin necesidad de login.
  - Habilitar carrito de compras para usuarios registrados.
  - Almacenar pedidos y enviar notificación de compra.

- [ ] **Dispositivos Inteligentes**
  - Integrar conectores para Google Fit, Apple Health y Samsung Health (real o simulado).

- [ ] **Interoperabilidad Clínica**
  - Permitir exportación y descarga de datos en formato FHIR.
  - Mostrar historial de métricas al usuario.

- [ ] **Notificaciones**
  - Enviar push notifications via Firebase.
  - Mostrar banners in‑app con alertas dinámicas.
  - Disparar emails mediante n8n en eventos clave.

- [ ] **Influencer Marketing**
  - Permitir a cualquier usuario activar su perfil embajador con código de referido.
  - Completar dashboard con referidos, ventas, comisión y opción de retiro.

- [x] **Estructura de Archivos**
  - Las plantillas `login.html`, `register.html` y `reset_password.html` están ubicadas en `frontend/webapp/templates/auth/`.
  - Se verificaron los nombres exactos de `quienes_somos.html`, `inversionistas.html`, `planes_prime.html` y `contacto.html`.
  - Existen `terms_and_conditions.html`, `privacy_policy.html` y `pqr.html` en la carpeta de páginas públicas.
