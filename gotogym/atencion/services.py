"""Crear una solicitud de atencion y avisar al equipo y a la persona.

`crear_solicitud` devuelve la solicitud ya guardada y con radicado. Los correos
se envian despues de confirmar la transaccion: si fallan, la solicitud sigue
existiendo y el resultado lo dice (`correo_cliente_enviado`), de modo que
nadie afirme que se envio un correo que no salio.
"""
import logging

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from gotogym import correo

from .models import SolicitudAtencion

logger = logging.getLogger(__name__)
MAX_MENSAJE = 1000


def _radicado(solicitud):
    return f'GTG-{timezone.localdate(solicitud.creada).year}-{solicitud.pk:06d}'


def crear_solicitud(*, nombre, email, motivo, mensaje, origen, acepta_contacto, user=None):
    if not acepta_contacto:
        raise ValueError('acepta_contacto')
    with transaction.atomic():
        solicitud = SolicitudAtencion.objects.create(
            user=user if user is not None and user.is_authenticated else None,
            nombre=nombre.strip()[:120], email=email.strip(), motivo=motivo,
            mensaje=mensaje.strip()[:MAX_MENSAJE], origen=origen, acepta_contacto=True,
        )
        solicitud.radicado = _radicado(solicitud)
        solicitud.save(update_fields=['radicado'])
    _avisar(solicitud)
    return solicitud


def _avisar(solicitud):
    destino_equipo = getattr(settings, 'ATENCION_EMAIL', '') or 'support@gotogym.store'
    datos = [
        (_('Radicado'), solicitud.radicado),
        (_('Motivo'), solicitud.get_motivo_display()),
        (_('Nombre'), solicitud.nombre),
        (_('Correo'), solicitud.email),
        (_('Origen'), solicitud.get_origen_display()),
    ]
    equipo = correo.Correo(
        asunto=f'[{solicitud.radicado}] {solicitud.get_motivo_display()}',
        titulo=_('Nueva solicitud de atención'),
        bloques=[
            correo.datos(datos),
            correo.parrafo(solicitud.mensaje),
            correo.boton(_('Ver en el panel'), correo.url_absoluta(
                reverse('admin_atencion_detail', args=[solicitud.pk]))),
        ],
    )
    cliente = correo.Correo(
        asunto=_('Recibimos tu solicitud %(radicado)s') % {'radicado': solicitud.radicado},
        titulo=_('Recibimos tu solicitud'),
        bloques=[
            correo.parrafo(_('Hola %(nombre)s, una persona del equipo GoToGym te responderá a este correo.')
                           % {'nombre': solicitud.nombre}),
            correo.datos([(_('Radicado'), solicitud.radicado), (_('Motivo'), solicitud.get_motivo_display())]),
            correo.parrafo(_('Guarda este número: con él podemos encontrar tu caso más rápido.')),
        ],
    )
    campos = []
    try:
        correo.enviar_correo(destino_equipo, equipo)
        solicitud.correo_equipo_enviado = True
        campos.append('correo_equipo_enviado')
    except Exception:
        logger.exception('Atencion: no se pudo avisar al equipo de %s.', solicitud.radicado)
    try:
        correo.enviar_correo(solicitud.email, cliente)
        solicitud.correo_cliente_enviado = True
        campos.append('correo_cliente_enviado')
    except Exception:
        logger.exception('Atencion: no se pudo enviar la confirmacion de %s.', solicitud.radicado)
    if campos:
        solicitud.save(update_fields=campos)
