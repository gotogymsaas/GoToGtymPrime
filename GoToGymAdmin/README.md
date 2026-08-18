# GoToGym Administracion

Panel administrativo independiente para gestionar productos, imagenes, categorias, marcas y visualizar usuarios inscritos.

## Conexion con la web comercial

Este proyecto usa la misma base de datos local de la tienda comercial:

`..\gotogym\db_local.sqlite3`

Tambien usa la misma carpeta de imagenes cargadas:

`..\gotogym\media`

Por eso, al crear o editar productos desde este panel, la web comercial de GoToGym ve los cambios en sus listados y carrito.

## Ejecucion

Ejecuta:

`EJECUTAR_ADMIN_GOTOGYM.bat`

El panel abre en:

`http://127.0.0.1:8002/`

## Administrador inicial

Usuario/email: `admin@gotogym.com`

Contrasena: `EricViana@2026`

El archivo `.bat` crea o actualiza este usuario como administrador Eric Viana cada vez que se ejecuta.

## Datos iniciales del catalogo

El archivo `.bat` tambien crea automaticamente la marca `GoToGym` y estas categorias si no existen:

- Conjuntos para dama
- Leggins
- Shorts para dama
- Tops
- Conjuntos para caballeros
- Chaquetas
- Sudaderas
- Shorts para caballeros
