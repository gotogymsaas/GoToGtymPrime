# Estructura de carpetas simplificada

Este documento resume la organización base del proyecto *GoToGym* para un desarrollo modular y escalable.

```
/ (repo root)
├── gotogym/                     # Proyecto Django legado
├── go-to-gym-platform/          # Nueva plataforma modular
│   ├── backend/                 # API central y microservicios en Django
│   │   ├── core_api/            # Apps reutilizables (auth, ecommerce, etc.)
│   │   └── services/            # Microservicios independientes
│   ├── frontend/                # Aplicación web Next.js (PWA)
│   ├── integrations/            # Clientes para APIs de terceros
│   ├── infrastructure/          # Docker, nginx y archivos de despliegue
│   └── docs/                    # Documentación y guías
└── integrations/                # Paquetes de integración instalables
```

La carpeta `frontend/mobile` se eliminó por estar vacía y para evitar confusión. El directorio `go-to-gym-platform/backend/services/wellness_monitor` incluye un microservicio de ejemplo. Utiliza esta estructura como referencia para nuevos componentes y mantén cada parte lo más aislada posible.
