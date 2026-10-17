"""Correos con la marca de GoToGym.

Un mismo contenido se envia como HTML de marca y como texto plano. El texto
es el respaldo para quien lee sin imagenes o en un cliente que no muestra
HTML, y tambien lo que ven las pruebas: por eso sale del mismo contenido y no
de un segundo texto que pueda desalinearse.

Quien escribe un correo arma un `Correo` con bloques (`parrafo`, `aviso`,
`productos`, `totales`, `datos`, `boton`) y llama a `enviar_correo`. La plantilla
(`templates/correo/`) decide como se ve; ningun correo trae su propio HTML.

Es una utilidad compartida: no conoce ninguna app.
"""
from dataclasses import dataclass, field

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

FIRMA_TEXTO = ('Equipo GoToGym', 'support@gotogym.store')


def parrafo(texto):
    return {'tipo': 'parrafo', 'texto': texto}


def aviso(texto):
    """Recuadro con borde de color, para lo que no debe pasar desapercibido."""
    return {'tipo': 'aviso', 'texto': texto}


def productos(lineas):
    """`lineas`: diccionarios con `nombre`, `detalle`, `cantidad`, `total` y,
    si hay, `imagen` (direccion absoluta)."""
    return {'tipo': 'productos', 'lineas': list(lineas)}


def totales(filas):
    """`filas`: tuplas `(etiqueta, valor)`; la ultima se destaca."""
    filas = list(filas)
    return {
        'tipo': 'totales',
        'filas': [
            {'etiqueta': etiqueta, 'valor': valor, 'destacada': i == len(filas) - 1}
            for i, (etiqueta, valor) in enumerate(filas)
        ],
    }


def datos(filas):
    """`filas`: tuplas `(etiqueta, valor)` en un recuadro de datos clave."""
    return {'tipo': 'datos', 'filas': [{'etiqueta': e, 'valor': v} for e, v in filas]}


def boton(texto, url, texto_plano=None):
    """Boton con enlace. `texto_plano` es la frase completa que lleva el
    enlace en la version de texto; sin ella se usa `texto: url`."""
    return {'tipo': 'boton', 'texto': texto, 'url': url, 'texto_plano': texto_plano}


@dataclass
class Correo:
    asunto: str
    titulo: str
    bloques: list = field(default_factory=list)
    kicker: str = ''
    saludo: str = ''
    previa: str = ''
    pie: str = ''

    def texto(self):
        partes = []
        if self.saludo:
            partes.append(self.saludo)
        for bloque in self.bloques:
            partes.append(_texto_del_bloque(bloque))
        partes.append('\n'.join(FIRMA_TEXTO))
        return '\n\n'.join(parte for parte in partes if parte) + '\n'

    def _previa(self):
        """Texto que el cliente de correo muestra junto al asunto en la
        bandeja: el indicado o, si no, el inicio del primer parrafo."""
        if self.previa:
            return self.previa
        for bloque in self.bloques:
            if bloque['tipo'] == 'parrafo':
                return bloque['texto'][:140]
        return ''

    def html(self):
        return render_to_string('correo/mensaje.html', {
            'correo': self,
            'previa': self._previa(),
            'sitio_url': settings.SITIO_URL,
        })


def _texto_del_bloque(bloque):
    tipo = bloque['tipo']
    if tipo in ('parrafo', 'aviso'):
        return bloque['texto']
    if tipo == 'productos':
        return '\n'.join(
            f"- {linea['nombre']} ({linea['detalle']}) x{linea['cantidad']}: {linea['total']}"
            for linea in bloque['lineas']
        )
    if tipo == 'totales':
        return '\n'.join(f"{fila['etiqueta']}: {fila['valor']}" for fila in bloque['filas'])
    if tipo == 'datos':
        return '\n'.join(f"{fila['etiqueta']}: {fila['valor']}" for fila in bloque['filas'])
    if tipo == 'boton':
        return bloque['texto_plano'] or f"{bloque['texto']}: {bloque['url']}"
    raise ValueError(f'Bloque de correo desconocido: {tipo!r}')


def url_absoluta(ruta):
    """Direccion publica de una ruta del sitio (un correo se lee fuera del
    sitio: sus imagenes y enlaces no pueden ser relativos)."""
    if str(ruta).startswith(('http://', 'https://')):
        return str(ruta)
    return f'{settings.SITIO_URL}{ruta}'


def enviar_correo(destinatario, correo):
    """Envia `correo` con su version HTML. Un fallo se propaga: quien llama
    decide si deshace algo o solo lo registra."""
    mensaje = EmailMultiAlternatives(
        subject=correo.asunto, body=correo.texto(), from_email=None, to=[destinatario],
    )
    mensaje.attach_alternative(correo.html(), 'text/html')
    return mensaje.send()
