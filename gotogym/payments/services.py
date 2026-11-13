"""Reembolso real de un pedido ya pagado.

Sustituye el `internal_note` manual ("Requiere reembolso manual") por un
`Refund` que efectivamente llama al proveedor de pago -- el mismo que
proceso el cobro original, no necesariamente el proveedor activo hoy.
"""
import uuid
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from .models import PaymentTransaction, Refund
from .providers.base import RefundRejected
from .providers.mercadopago import MercadoPagoPaymentProvider
from .providers.mock import MockPaymentProvider

_PROVIDERS_BY_NAME = {
    'mock': MockPaymentProvider,
    'mercadopago': MercadoPagoPaymentProvider,
}


# Un reembolso pendiente mas reciente que esto puede seguir en curso en otra
# peticion: conciliarlo antes marcaria como fallido uno que esta por terminar.
MINUTOS_MINIMOS_PARA_CONCILIAR = 5

# Estados con los que el proveedor da un reembolso por no hecho.
_ESTADOS_FALLIDOS = {'rejected', 'cancelled'}


class RefundError(Exception):
    """Error de negocio que impide procesar el reembolso."""


def get_provider_for_transaction(payment_transaction):
    """El proveedor que efectivamente proceso ese pago.

    Deliberadamente no usa `payments.views.get_active_provider()`: una
    transaccion vieja se reembolsa con el proveedor que la cobro, aunque el
    proveedor activo del sitio haya cambiado despues.
    """
    clase = _PROVIDERS_BY_NAME.get(payment_transaction.provider)
    if clase is None:
        raise RefundError(f"Proveedor de pago desconocido: {payment_transaction.provider!r}.")
    return clase()


def refund_order_payment(order, requested_by, amount=None):
    """Reembolsa el pago aprobado de un pedido y deja constancia en `Refund`.

    No cambia `order_status`: el pedido ya deberia estar cancelado o
    marcado como devolucion antes de llamar esto (esa transicion ya revierte
    la comision del afiliado por separado, ver `orders.services`).

    Se hace en tres tiempos para que ningun fallo borre el rastro de lo que
    se intento: (1) con la transaccion de pago bloqueada se valida y se
    registra el reembolso como pendiente; (2) fuera de toda transaccion se
    llama al proveedor, con la clave de idempotencia del registro; (3) se
    anota el resultado. Si el proveedor rechaza la solicitud queda un
    `Refund` fallido; si el proceso muere entre (2) y (3) queda uno pendiente
    que bloquea nuevos intentos hasta conciliarlo contra el proveedor, en vez
    de arriesgar devolver el dinero dos veces (ver `conciliar_reembolso`).

    El resultado queda asi: aprobado si el proveedor lo aprueba; fallido si lo
    rechaza (estado `rejected`/`cancelled` o un `RefundRejected`), porque
    entonces se sabe que el dinero no salio; pendiente en cualquier otro
    caso, incluido un error de red o un tiempo agotado, donde no se sabe si el
    reembolso llego a hacerse.
    """
    with db_transaction.atomic():
        transaccion = (
            PaymentTransaction.objects.select_for_update()
            .filter(order=order, status=PaymentTransaction.Status.APPROVED)
            .order_by('-created_at')
            .first()
        )
        if transaccion is None:
            raise RefundError('Este pedido no tiene un pago aprobado para reembolsar.')

        if transaccion.refunds.filter(status=Refund.Status.APPROVED).exists():
            raise RefundError('Este pago ya fue reembolsado.')
        if transaccion.refunds.filter(status=Refund.Status.PENDING).exists():
            raise RefundError(
                'Ya hay un reembolso en curso para este pago. Verifica su estado con el proveedor '
                'antes de intentarlo de nuevo.'
            )

        monto = Decimal(amount) if amount is not None else transaccion.amount
        if monto <= 0 or monto > transaccion.amount:
            raise RefundError('El monto a reembolsar debe ser mayor que cero y no superar el pago.')
        provider = get_provider_for_transaction(transaccion)

        reembolso = Refund.objects.create(
            payment_transaction=transaccion, amount=monto, status=Refund.Status.PENDING,
            requested_by=requested_by, idempotency_key=uuid.uuid4().hex,
        )

    try:
        resultado = provider.refund_payment(
            transaccion, amount=amount, idempotency_key=reembolso.idempotency_key,
        )
    except RefundRejected as error:
        reembolso.status = Refund.Status.FAILED
        reembolso.error_message = str(error)
        reembolso.save(update_fields=['status', 'error_message'])
        raise RefundError(f'El proveedor de pago rechazo el reembolso: {error}') from error
    except Exception as error:
        reembolso.error_message = str(error)
        reembolso.save(update_fields=['error_message'])
        raise RefundError(
            'No se pudo confirmar el resultado del reembolso con el proveedor de pago. '
            'Queda pendiente: verifica su estado antes de intentarlo de nuevo.'
        ) from error

    estado = resultado.get('status')
    if estado == 'approved':
        reembolso.status = Refund.Status.APPROVED
    elif estado in _ESTADOS_FALLIDOS:
        reembolso.status = Refund.Status.FAILED
        reembolso.error_message = f'El proveedor respondio con estado {estado}.'
    reembolso.provider_refund_id = resultado.get('provider_refund_id', '')
    reembolso.save(update_fields=['status', 'provider_refund_id', 'error_message'])
    if reembolso.status == Refund.Status.FAILED:
        raise RefundError(f'El proveedor de pago rechazo el reembolso: {estado}.')
    return reembolso


def conciliar_reembolso(reembolso):
    """Resuelve un reembolso pendiente consultando al proveedor.

    Se busca el reembolso en la lista del proveedor, primero por su id (si la
    solicitud original llego a recibir uno) y si no por monto entre los que
    ningun otro registro reclama. Tres salidas:

    * aprobado en el proveedor -> aprobado;
    * rechazado o cancelado, o ausente de la lista -> fallido (se sabe que el
      dinero no salio) y se puede pedir de nuevo;
    * presente en cualquier otro estado (por ejemplo `in_process`) -> sigue
      pendiente, sin tocarlo: el dinero puede estar saliendo.

    Devuelve el reembolso. No hace nada con uno que no este pendiente y se
    niega a conciliar uno demasiado reciente, cuya peticion puede seguir en
    curso."""
    if reembolso.status != Refund.Status.PENDING:
        return reembolso
    antiguedad = timezone.now() - reembolso.created_at
    if antiguedad.total_seconds() < MINUTOS_MINIMOS_PARA_CONCILIAR * 60:
        raise RefundError('El reembolso es muy reciente para conciliarlo: puede seguir en curso.')

    transaccion = reembolso.payment_transaction
    provider = get_provider_for_transaction(transaccion)
    try:
        registrados = provider.list_refunds(transaccion)
    except NotImplementedError:
        raise RefundError('El proveedor de este pago no permite consultar sus reembolsos.') from None
    except Exception as error:
        raise RefundError(f'No se pudo consultar al proveedor: {error}') from error

    registrado = _buscar_en_el_proveedor(reembolso, transaccion, registrados)

    if registrado is None:
        reembolso.status = Refund.Status.FAILED
        reembolso.error_message = 'El proveedor no tiene registrado este reembolso.'
        reembolso.save(update_fields=['status', 'error_message'])
        return reembolso

    estado = registrado['status']
    reembolso.provider_refund_id = registrado['provider_refund_id']
    if estado == 'approved':
        reembolso.status = Refund.Status.APPROVED
    elif estado in _ESTADOS_FALLIDOS:
        reembolso.status = Refund.Status.FAILED
        reembolso.error_message = f'El proveedor respondio con estado {estado}.'
    reembolso.save(update_fields=['status', 'provider_refund_id', 'error_message'])
    return reembolso


def _buscar_en_el_proveedor(reembolso, transaccion, registrados):
    """El registro del proveedor que corresponde a `reembolso`, o None."""
    if reembolso.provider_refund_id:
        for registrado in registrados:
            if registrado['provider_refund_id'] == reembolso.provider_refund_id:
                return registrado
        return None

    reclamados = set(
        transaccion.refunds.exclude(pk=reembolso.pk).exclude(provider_refund_id='')
        .values_list('provider_refund_id', flat=True)
    )
    candidatos = [
        r for r in registrados
        if r['amount'] == reembolso.amount and r['provider_refund_id'] not in reclamados
    ]

    def prioridad(registrado):
        if registrado['status'] == 'approved':
            return 0
        return 2 if registrado['status'] in _ESTADOS_FALLIDOS else 1

    return min(candidatos, key=prioridad) if candidatos else None
