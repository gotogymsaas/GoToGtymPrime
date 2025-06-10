# GoToGym Plataforma - Arquitectura y Tecnologías

Esta guía resume las librerías, dependencias y herramientas recomendadas para cada carpeta principal del proyecto. Sirve como referencia para iniciar el desarrollo de una plataforma escalable que incluya PWA, microservicios con agentes de IA, ecommerce, CRM, pasarelas de pago, dispositivos wearables e historia clínica interoperable.

## frontend/
**Tecnologías clave:** Next.js, React, Tailwind, Capacitor, i18next

| Tipo | Paquete / Herramienta | Propósito |
| --- | --- | --- |
| Framework | `next`, `react`, `react-dom` | Base del frontend web |
| Estilos | `tailwindcss`, `autoprefixer`, `postcss` | Estilizado responsivo |
| Animaciones | `framer-motion`, `gsap`, `aos` | Animaciones de lujo y scroll |
| Internacionalización | `next-i18next`, `i18next-browser-languagedetector` | Multilenguaje |
| Formulario + validación | `react-hook-form`, `yup` | Registro, login y datos seguros |
| Auth client | `next-auth`, `axios`, `js-cookie` | Gestión de sesión |
| Chatbot UI | `react-chatbot-kit` o `@headlessui/react` | UI del chat con IA |
| Mobile integration | `@capacitor/core`, `@capacitor/app`, `@capacitor/push-notifications` | Empaquetado iOS/Android |
| PWA | `next-pwa`, `workbox` | Funcionalidad offline / instalación |
| Visualización | `recharts`, `nivo`, `chart.js` | Progreso, métricas, ventas influencer |

## backend/
**Tecnologías clave:** Django, Django REST Framework, PostgreSQL

| Tipo | Paquete / Herramienta | Propósito |
| --- | --- | --- |
| Framework principal | `Django>=5.2` | Backend central |
| API REST | `djangorestframework`, `drf-yasg` | Endpoints JSON + documentación Swagger |
| Autenticación | `django-allauth`, `django-rest-auth` | Registro seguro y JWT |
| Base de datos | `psycopg2`, `dj-database-url` | PostgreSQL y variables de entorno |
| Gestión de usuarios | `django-custom-user`, `django-cors-headers` | Perfil extendido y seguridad frontend |
| Ecommerce | `django-oscar`, `django-payments` | Manejo de productos y pagos |
| Seguridad avanzada | `django-axes`, `django-secure`, `bcrypt` | Seguridad en login y sesiones |
| Exportación clínica | `fhir.resources`, `weasyprint` | Generar historia clínica descargable |
| Testing | `pytest`, `pytest-django`, `coverage` | Pruebas automáticas |

## services/
**Tecnologías clave:** LangChain, OpenAI, FastAPI, n8n

| Microservicio IA | Herramienta / Paquete | Propósito |
| --- | --- | --- |
| Orquestador IA | `langchain`, `openai`, `transformers`, `dotenv` | Control y flujo de conversaciones |
| Agente de entrenamiento | `torch`, `sklearn`, `numpy`, `pandas` | Rutinas personalizadas y tracking |
| Agente de nutrición | `nutritionix`, `google-cloud-vision`, `firebase-admin` | Escaneo alimentos, consulta APIs |
| Wellness / salud | `fitbit`, `google-fit`, `apple-healthkit`, `aiohttp` | Wearables, frecuencia cardíaca, pasos |
| Mensajería motivacional | `nltk`, `spacy`, `textblob` | Generación de mensajes emocionales |
| Framework | `FastAPI`, `uvicorn`, `pydantic` | Microservicios IA rápidos, escalables |

## integrations/
**Tecnologías clave:** API REST, webhooks, OAuth2, n8n

| Servicio | Herramienta / API | Propósito |
| --- | --- | --- |
| CRM | HubSpot CRM API, `requests` | Webhooks de registro, contacto y venta |
| Pasarela de pagos | MercadoPago API, `stripe` (respaldo) | Checkout, webhook pagos exitosos |
| Contabilidad | Alegra API, `json`, `requests`, `uuid` | Facturación electrónica y gastos |
| Dispositivos inteligentes | Google Fit API, Apple HealthKit, Samsung Health SDK | Datos biométricos, hábitos |
| Automatización | n8n (auto-hosted o SaaS) | Flujos de tareas entre APIs |
| Seguridad | `oauthlib`, `requests-oauthlib` | Autenticación con proveedores externos |

## infrastructure/
**Tecnologías clave:** Docker, Nginx, CI/CD

| Componente | Herramienta / Archivo | Propósito |
| --- | --- | --- |
| Contenedores | Docker, Docker Compose | Entorno aislado por microservicio |
| Servidor proxy | Nginx, certbot, Let's Encrypt | HTTPS + reverse proxy |
| CI/CD | GitHub Actions, GitLab CI, Terraform | Despliegue automático |
| Variables de entorno | `.env`, `dotenv`, `secrets.json` | Configuración segura |
| Logs y monitoreo | Sentry, Prometheus, Grafana, LogDNA | Observabilidad |
| Infraestructura cloud | Render, Vercel, Railway, GCP, AWS | Hosting de microservicios y frontend |
| Almacenamiento | Cloudinary, AWS S3, Firebase Storage | Imagenes, archivos usuario, PDFs historia clínica |

Este documento sirve como punto de partida para organizar el repositorio y planificar las dependencias de cada componente del sistema.
