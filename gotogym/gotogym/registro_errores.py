"""Registro de errores en un archivo de texto.

Todo lo que Django o la aplicacion reporten como WARNING o superior (paginas
no encontradas, accesos denegados, excepciones no controladas, fallos de
integraciones) termina en `logs/errores.txt`, una linea por evento y con el
traceback debajo cuando existe. El archivo rota solo, para no crecer sin
limite.

El contexto de la peticion (IP, usuario, metodo, ruta, referencia) lo agrega
`ContextoDePeticion`: `django.request` ya adjunta la peticion y el codigo de
estado a cada registro, asi que ninguna vista tiene que loguear a mano.
"""
import logging
import uuid
from pathlib import Path

NOMBRE_ARCHIVO = 'errores.txt'
FORMATO = (
    '%(asctime)s | %(levelname)s | %(estado)s | ref=%(referencia)s | ip=%(ip)s | '
    'usuario=%(usuario)s | %(metodo)s %(ruta)s | %(name)s | %(message)s'
)


def referencia_de(request):
    """Codigo corto que identifica el error de esta peticion.

    Es el mismo que se muestra en la pagina de error y el que se escribe en
    el log, de modo que quien reporta un fallo pueda darlo y se encuentre la
    linea exacta. Se genera una sola vez por peticion."""
    if not hasattr(request, 'referencia_error'):
        request.referencia_error = uuid.uuid4().hex[:8].upper()
    return request.referencia_error


class ContextoDePeticion(logging.Filter):
    """Completa cada registro con los datos de la peticion que lo origino.

    Solo se guarda el id del usuario (no su correo) y la ruta sin la cadena de
    consulta: el log no debe acumular datos personales ni tokens que viajen en
    la URL. Los registros que no vienen de una peticion (tareas, comandos) se
    escriben con guiones."""

    def filter(self, record):
        # Import tardio: settings.py importa este modulo y ratelimit toca la cache.
        from .ratelimit import ip_del_cliente

        request = getattr(record, 'request', None)
        record.estado = getattr(record, 'status_code', '-')
        record.referencia = record.ip = record.usuario = record.metodo = record.ruta = '-'
        if hasattr(request, 'META'):
            record.referencia = referencia_de(request)
            record.ip = ip_del_cliente(request)
            record.metodo = request.method
            record.ruta = request.path
            usuario = getattr(request, 'user', None)
            if usuario is not None and usuario.is_authenticated:
                record.usuario = usuario.pk
            else:
                record.usuario = 'anonimo'
        return True


def configuracion_logging(directorio):
    """Diccionario LOGGING con el archivo de errores en `directorio`.

    Si el directorio no se puede crear o escribir (disco de solo lectura en
    un despliegue), el servidor sigue arrancando y los errores quedan solo en
    la consola: perder el archivo no debe tumbar el sitio."""
    handlers = {}
    try:
        directorio = Path(directorio)
        directorio.mkdir(parents=True, exist_ok=True)
        ruta = directorio / NOMBRE_ARCHIVO
        with ruta.open('a', encoding='utf-8'):
            pass
    except OSError:
        return {'version': 1, 'disable_existing_loggers': False}

    handlers['archivo_errores'] = {
        'class': 'logging.handlers.RotatingFileHandler',
        'level': 'WARNING',
        'filename': str(ruta),
        'maxBytes': 5 * 1024 * 1024,
        'backupCount': 5,
        'encoding': 'utf-8',
        'formatter': 'errores',
        'filters': ['contexto_peticion'],
    }
    handlers['consola'] = {
        'class': 'logging.StreamHandler',
        'level': 'WARNING',
        'formatter': 'errores',
        'filters': ['contexto_peticion'],
    }
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'filters': {
            'contexto_peticion': {'()': 'gotogym.registro_errores.ContextoDePeticion'},
        },
        'formatters': {
            'errores': {'format': FORMATO},
        },
        'handlers': handlers,
        # El logger raiz recibe tambien lo que propagan `django.request`,
        # `django.security` y los loggers de cada app (payments, orders...).
        'root': {'handlers': ['archivo_errores', 'consola'], 'level': 'WARNING'},
    }
