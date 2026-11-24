"""Puente entre el navegador y el Coach.

El navegador nunca habla con el Coach: envia aqui el mensaje (con el token
CSRF de la sesion) y esta vista arma el paquete con datos del servidor, lo
firma, lo envia y devuelve una respuesta ya validada. Todas las respuestas son
JSON con `ok` y, si falla, un `error` de una lista corta de codigos; los textos
que ve la persona los pone el panel (traducidos), no el servidor.

Nunca se escribe el texto del mensaje en logs ni en Sentry.

Un modulo por canal (`texto`, `subida_foto`, `subida_archivo`, `subida_voz`)
y lo que comparten en `comun`. Este paquete reexporta lo que `vendedor.urls` y
las pruebas importan; quien sustituye una funcion en una prueba apunta al
modulo donde se usa (por ejemplo `vendedor.views.comun._ahora`).
"""
from .comun import SEGUNDOS_DIA, _ahora, _diagnostico_para, _SubidaEnMemoria
from .subida_archivo import MAX_BYTES_PETICION_DOCUMENTO, documento_vista
from .subida_foto import MAX_BYTES_PETICION_IMAGEN, imagen_vista
from .subida_voz import MAX_BYTES_PETICION_VOZ, voz_vista
from .texto import identidad_estado, mensaje

__all__ = [
    'MAX_BYTES_PETICION_DOCUMENTO',
    'MAX_BYTES_PETICION_IMAGEN',
    'MAX_BYTES_PETICION_VOZ',
    'SEGUNDOS_DIA',
    '_SubidaEnMemoria',
    '_ahora',
    '_diagnostico_para',
    'documento_vista',
    'identidad_estado',
    'imagen_vista',
    'mensaje',
    'voz_vista',
]
