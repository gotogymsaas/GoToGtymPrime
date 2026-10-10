"""Correos del programa de afiliados.

Cada funcion es una tarea para `gotogym.tasks.enqueue`: vive a nivel de
modulo y recibe solo datos simples (ids y texto). Un fallo de correo nunca
debe deshacer la accion que lo origino, asi que se deja en el log.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from .models import Commission, PerfilAfiliado

logger = logging.getLogger(__name__)

FIRMA = 'Equipo GoToGym\nsupport@gotogym.store\n'


def _enlace(nombre_de_ruta):
    return f'{settings.SITIO_URL}{reverse(nombre_de_ruta)}'


def _fecha(momento):
    return f'{timezone.localtime(momento):%d/%m/%Y}'


def _enviar(usuario, asunto, cuerpo):
    try:
        send_mail(subject=asunto, message=cuerpo, from_email=None, recipient_list=[usuario.email])
    except Exception:
        logger.exception('No se pudo enviar el correo "%s" a %s', asunto, usuario.pk)


def _perfil(perfil_id):
    return PerfilAfiliado.objects.select_related('user').get(pk=perfil_id)


def _saludo(usuario):
    return f'Hola {usuario.first_name or usuario.email},\n\n'


def solicitud_recibida(perfil_id):
    perfil = _perfil(perfil_id)
    _enviar(
        perfil.user, 'Recibimos tu solicitud al programa de afiliados de GoToGym',
        f'{_saludo(perfil.user)}'
        'Recibimos tu solicitud para ser afiliado de GoToGym. El equipo revisara tus datos y tus redes '
        'y te escribiremos cuando tengamos una respuesta.\n\n'
        f'Puedes seguir el estado desde tu panel: {_enlace("afiliado_dashboard")}\n\n{FIRMA}',
    )


def afiliado_aprobado(perfil_id):
    perfil = _perfil(perfil_id)
    enlace = f'{settings.SITIO_URL}{reverse("home")}?ref={perfil.referral_code}'
    _enviar(
        perfil.user, 'Ya eres afiliado de GoToGym',
        f'{_saludo(perfil.user)}'
        'Tu solicitud fue aprobada. Ya eres afiliado de GoToGym.\n\n'
        f'Tu codigo: {perfil.referral_code}\n'
        f'Tu enlace para compartir: {enlace}\n\n'
        f'Desde tu panel puedes ver tus ventas y comisiones, e inscribir tu cuenta Bre-B para cobrar: '
        f'{_enlace("afiliado_dashboard")}\n\n'
        'Recuerda identificar como publicidad el contenido en el que uses tu codigo.\n\n'
        f'{FIRMA}',
    )


def afiliado_rechazado(perfil_id):
    perfil = _perfil(perfil_id)
    motivo = f'Motivo: {perfil.rejection_reason}\n\n' if perfil.rejection_reason else ''
    _enviar(
        perfil.user, 'Sobre tu solicitud al programa de afiliados de GoToGym',
        f'{_saludo(perfil.user)}'
        'Revisamos tu solicitud y, por ahora, no podemos aprobarla.\n\n'
        f'{motivo}'
        f'Si crees que las condiciones cambiaron, puedes volver a postularte desde {_enlace("afiliado_suscribete")}.\n\n'
        f'{FIRMA}',
    )


def baja_solicitada(perfil_id):
    perfil = _perfil(perfil_id)
    _enviar(
        perfil.user, 'Recibimos tu aviso de baja del programa de afiliados',
        f'{_saludo(perfil.user)}'
        f'Registramos tu aviso de baja el {_fecha(perfil.exit_requested_at)}. '
        f'Tu baja sera efectiva el {_fecha(perfil.exit_effective_at)} (15 dias despues del aviso). '
        'Hasta esa fecha tu codigo y tu panel siguen activos.\n\n'
        'Las comisiones que hayas confirmado por encima del minimo de pago se liquidan en el siguiente ciclo de pagos. '
        f'Si cambias de opinion, puedes cancelar la baja desde tu panel: {_enlace("afiliado_dashboard")}\n\n'
        f'{FIRMA}',
    )


def baja_efectiva(perfil_id):
    perfil = _perfil(perfil_id)
    _enviar(
        perfil.user, 'Tu baja del programa de afiliados ya es efectiva',
        f'{_saludo(perfil.user)}'
        'Tu baja del programa de afiliados de GoToGym ya es efectiva: dejamos de rastrear compras con tu codigo. '
        'Puedes seguir entrando a tu panel para ver y solicitar el pago de tus comisiones confirmadas.\n\n'
        f'{FIRMA}',
    )


def terminacion(perfil_id):
    perfil = _perfil(perfil_id)
    motivo = perfil.get_exit_reason_display()
    notas = f'\n{perfil.exit_notes}' if perfil.exit_notes else ''
    _enviar(
        perfil.user, 'Terminamos tu participacion en el programa de afiliados',
        f'{_saludo(perfil.user)}'
        'Terminamos tu participacion en el programa de afiliados de GoToGym y desactivamos tu codigo.\n\n'
        f'Motivo: {motivo}.{notas}\n\n'
        'Las comisiones validas y confirmadas que superen el minimo se pagan en el siguiente ciclo; '
        'las asociadas a ventas fraudulentas o que incumplen los terminos se invalidan. '
        'Si tienes dudas, escribenos a support@gotogym.store.\n\n'
        f'{FIRMA}',
    )


def validacion_extendida(comision_id):
    comision = Commission.objects.select_related('afiliado__user', 'order').get(pk=comision_id)
    usuario = comision.afiliado.user
    _enviar(
        usuario, 'Extendimos el periodo de validacion de una comision',
        f'{_saludo(usuario)}'
        f'Extendimos el periodo de validacion de tu comision del pedido {comision.order.order_number} '
        f'hasta el {comision.validation_last_day:%d/%m/%Y}.\n\n'
        f'Motivo: {comision.extension_reason}\n\n'
        'Mientras tanto la comision sigue como pendiente en tu panel. '
        f'Si tienes dudas, escribenos a support@gotogym.store.\n\n{FIRMA}',
    )


def cambio_de_tasa(perfil_id, tasa):
    perfil = _perfil(perfil_id)
    _enviar(
        perfil.user, 'Cambio en tu comision del programa de afiliados',
        f'{_saludo(perfil.user)}'
        f'La comision por tus ventas pasa a ser del {tasa} %. El cambio aplica a las compras que se hagan con tu codigo '
        'a partir de hoy; las comisiones ya registradas conservan la tasa con la que se calcularon.\n\n'
        'Si no estas de acuerdo, puedes darte de baja sin penalizacion desde tu panel.\n\n'
        f'{FIRMA}',
    )


def aviso_general(perfil_id, asunto, mensaje):
    perfil = _perfil(perfil_id)
    _enviar(perfil.user, asunto, f'{_saludo(perfil.user)}{mensaje}\n\n{FIRMA}')
