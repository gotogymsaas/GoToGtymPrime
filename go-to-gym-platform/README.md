# Go-To-Gym Platform

Este directorio contiene la arquitectura modular de GoToGym. Se divide en distintos paquetes para frontend, backend, microservicios de IA, integraciones y herramientas de infraestructura. Consulta el documento [docs/tech-stack.md](docs/tech-stack.md) para ver la lista detallada de tecnologías y dependencias sugeridas.

La carpeta `frontend/webapp` ahora contiene una configuracion basica de Next.js con soporte para PWA usando `next-pwa`.

## Sistema de notificaciones

Se añadió una app `notifications` en `backend/core_api` con modelos para registrar tokens de dispositivo y un historial de notificaciones. Incluye vistas protegidas con JWT para enviar y listar notificaciones. En el frontend se añadieron utilidades para registrar el token de FCM y un componente `NotificationBanner` que muestra los mensajes dentro de la PWA. El service worker `firebase-messaging-sw.js` permite recibir notificaciones en segundo plano.
Se añadieron plantillas de ejemplo en `backend/core_api/notifications/templates/emails` para los correos de notificación.
