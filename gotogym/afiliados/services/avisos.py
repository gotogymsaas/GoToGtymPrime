"""Correos a los afiliados: aviso de pago de una comision y comunicados
generales."""
import logging

from django.utils import timezone
from gotogym.correo import Correo, datos, enviar_correo, parrafo
from gotogym.tasks import enqueue

from .. import correos
from ..models import EstadoAfiliado, PerfilAfiliado, WithdrawalRequest

# Nombre fijo (el del modulo que antes lo contenia todo): es el que los
# filtros de registro y las alertas ya conocen.
logger = logging.getLogger('afiliados.services')


def notify_commission_paid(solicitud_id):
    """Avisa por correo al afiliado que su solicitud de comision fue pagada,
    con el desglose de lo que recibe.

    Un fallo de correo nunca debe deshacer ni ocultar el pago ya registrado:
    se deja en el log y el administrador sigue su flujo.
    """
    from tienda.templatetags.tienda_filters import cop

    solicitud = WithdrawalRequest.objects.select_related('afiliado__user').get(pk=solicitud_id)
    usuario = solicitud.afiliado.user
    nombre = usuario.first_name or usuario.email
    bloques = [parrafo(
        f'Te confirmamos que pagamos tu solicitud de comisión por ${cop(solicitud.amount)} COP, '
        f'solicitada el {timezone.localtime(solicitud.requested_at):%d/%m/%Y}.'
    )]
    if solicitud.recovery_amount or solicitud.transaction_fee:
        filas = []
        if solicitud.recovery_amount:
            filas.append((
                'Descontado por pedidos devueltos o reembolsados (ya incluido en el monto)',
                f'${cop(solicitud.recovery_amount)} COP',
            ))
        if solicitud.transaction_fee:
            filas.append(('Gastos de transacción', f'${cop(solicitud.transaction_fee)} COP'))
        filas.append(('Total recibido', f'${cop(solicitud.net_paid)} COP'))
        bloques.append(datos(filas))
    bloques += [
        parrafo('Si tienes alguna duda sobre el pago, escríbenos a support@gotogym.store.'),
        parrafo('Gracias por hacer parte del programa de afiliados de GoToGym.'),
    ]
    correo = Correo(
        asunto='Tu comisión de GoToGym fue pagada', titulo='Tu comisión fue pagada', bloques=bloques,
        kicker='Programa de afiliados', saludo=f'Hola {nombre},',
        pie='Recibes este correo porque participas en el programa de afiliados de GoToGym.',
    )
    try:
        enviar_correo(usuario.email, correo)
    except Exception:
        logger.exception('No se pudo enviar el aviso de pago de comisión (solicitud %s)', solicitud.pk)


# --- Avisos a los afiliados ---------------------------------------------------

def perfiles_activos():
    return PerfilAfiliado.objects.filter(status=EstadoAfiliado.APPROVED, is_active=True)


def avisar_afiliados(asunto, mensaje):
    """Envia un aviso a todos los afiliados activos (cambio de terminos,
    del programa, etc.). Devuelve a cuantos."""
    ids = list(perfiles_activos().values_list('pk', flat=True))
    for perfil_id in ids:
        enqueue(correos.aviso_general, perfil_id, asunto, mensaje)
    return len(ids)


def avisar_cambio_de_tasa(nueva_tasa, afiliado=None):
    """Avisa de un cambio de comision: a un afiliado si tiene tasa propia, o
    a todos los que usan la tasa global. Aplica a ventas posteriores."""
    if afiliado is not None:
        destinatarios = [afiliado.pk]
    else:
        destinatarios = list(perfiles_activos().filter(commission_rate__isnull=True).values_list('pk', flat=True))
    for perfil_id in destinatarios:
        enqueue(correos.cambio_de_tasa, perfil_id, str(nueva_tasa))
    return len(destinatarios)
