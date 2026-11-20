"""Tarjetas de regalo virtuales: emision, canje y devolucion de saldo.

Reglas del negocio:

- Se compran por un valor entre `VALOR_MINIMO` y `VALOR_MAXIMO`, se pagan
  como cualquier pedido y se activan cuando el pago queda aprobado. Ahi se le
  envia el codigo a quien recibe el regalo.
- Vencen `MESES_DE_VIGENCIA` meses despues de activarse (la Circular Unica de
  la SIC, numeral 2.18, exige al menos un año). Canjear una parte no prorroga
  el plazo.
- Son un medio de pago, no un descuento: se combinan con un cupon (el cupon
  rebaja el precio y la tarjeta paga lo que queda, envio incluido) y lo
  pagado con ellas no rebaja la base de la factura ni la comision del
  afiliado. Comprar una tarjeta no genera comision ni factura: la venta ocurre
  cuando se canjea (doctrina DIAN, Oficio 16302 de 2019).
- Para canjearla hay que tener cuenta: el checkout ya exige sesion.

Todo cambio de saldo pasa por este modulo, con la tarjeta bloqueada, y deja
un `GiftCardMovement`. Este modulo no conoce `orders.services` (que lo usa):
no crea pedidos ni manda correos.
"""
import secrets
from datetime import datetime, time
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from .models import GiftCard, GiftCardMovement, GiftCardMovementKind, GiftCardStatus

VALOR_MINIMO = Decimal('50000')
VALOR_MAXIMO = Decimal('1000000')
VALORES_SUGERIDOS = (Decimal('50000'), Decimal('100000'), Decimal('200000'), Decimal('500000'))
MESES_DE_VIGENCIA = 12
LARGO_DEDICATORIA = 300

# Linea con la que la compra de una tarjeta aparece en el pedido.
SKU_TARJETA = 'TARJETA-REGALO'
NOMBRE_TARJETA = 'Tarjeta de regalo GoToGym'

# Sin 0/O ni 1/I: se dictan y se copian a mano. 32 simbolos en 16 posiciones
# son 80 bits, imposibles de adivinar a ciegas.
ALFABETO = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
LARGO_CODIGO = 16

# Tope de codigos equivocados por cuenta antes de bloquear la validacion un
# rato: frena a quien prueba codigos al azar desde el checkout.
INTENTOS_FALLIDOS_MAXIMOS = 10
VENTANA_DE_INTENTOS = 60 * 60

CERO = Decimal('0.00')


class TarjetaNoDisponible(Exception):
    """La tarjeta no se puede canjear (vencida, sin saldo, bloqueada...)."""


def normalizar_codigo(texto):
    """'abcd-efgh ijkl-mnpq' -> 'ABCDEFGHIJKLMNPQ'. Solo letras y digitos."""
    return ''.join(c for c in (texto or '').upper() if c.isalnum())


def generar_codigo():
    return ''.join(secrets.choice(ALFABETO) for _ in range(LARGO_CODIGO))


def fecha_de_vencimiento(desde):
    """Ultimo instante, en hora local, del mismo dia `MESES_DE_VIGENCIA` meses
    despues. Un 29 de febrero sin equivalente vence el 28."""
    dia = timezone.localtime(desde).date()
    meses = dia.month - 1 + MESES_DE_VIGENCIA
    anio, mes = dia.year + meses // 12, meses % 12 + 1
    try:
        vence = dia.replace(year=anio, month=mes)
    except ValueError:
        vence = dia.replace(year=anio, month=mes, day=28)
    return timezone.make_aware(datetime.combine(vence, time.max.replace(microsecond=0)))


def buscar_por_codigo(codigo):
    codigo = normalizar_codigo(codigo)
    if len(codigo) != LARGO_CODIGO:
        return None
    return GiftCard.objects.filter(code=codigo).first()


def buscar_tarjeta_usable(codigo):
    """La tarjeta del codigo si hoy se puede canjear; None en otro caso."""
    tarjeta = buscar_por_codigo(codigo)
    if tarjeta is None or not tarjeta.is_usable():
        return None
    return tarjeta


def motivo_no_usable(tarjeta):
    """Por que una tarjeta existente no se puede canjear, para decirselo a
    quien la tiene en vez de un "no valida" generico."""
    if tarjeta.status == GiftCardStatus.ACTIVE and tarjeta.is_expired():
        return 'expired'
    if tarjeta.status == GiftCardStatus.ACTIVE and tarjeta.balance <= 0:
        return 'no_balance'
    return 'invalid'


# ---------------------------------------------------------------- intentos

def _clave_de_intentos(user):
    return f'tarjeta_regalo:fallos:{getattr(user, "pk", None) or "anonimo"}'


def demasiados_intentos(user):
    if not getattr(settings, 'RATE_LIMIT_ENABLED', True):
        return False
    return (cache.get(_clave_de_intentos(user)) or 0) >= INTENTOS_FALLIDOS_MAXIMOS


def registrar_intento_fallido(user):
    """Cuenta un codigo equivocado. No es atomico con todos los backends de
    cache; basta para frenar el abuso, no es un cupo estricto."""
    clave = _clave_de_intentos(user)
    cache.set(clave, (cache.get(clave) or 0) + 1, timeout=VENTANA_DE_INTENTOS)


# ---------------------------------------------------------------- emision

def crear_tarjeta_pendiente(order, comprador, valor, remitente, destinatario, correo, dedicatoria, idioma):
    """Crea la tarjeta de una compra, todavia sin activar. Se llama dentro de
    la transaccion que crea el pedido."""
    for _intento in range(5):
        try:
            with transaction.atomic():
                return GiftCard.objects.create(
                    code=generar_codigo(),
                    initial_amount=valor,
                    balance=valor,
                    purchase_order=order,
                    buyer=comprador if getattr(comprador, 'is_authenticated', False) else None,
                    sender_name=remitente,
                    recipient_name=destinatario,
                    recipient_email=correo,
                    message=dedicatoria,
                    language=idioma or 'es',
                )
        except IntegrityError:
            continue
    raise IntegrityError('No se pudo generar un código único para la tarjeta de regalo.')


def activar_compra(order, momento=None):
    """Activa la tarjeta de una compra cuyo pago se aprobo. Idempotente:
    devuelve la tarjeta, o None si la compra no tiene tarjeta pendiente."""
    tarjeta = GiftCard.objects.select_for_update().filter(purchase_order=order).first()
    if tarjeta is None or tarjeta.status != GiftCardStatus.PENDING:
        return None
    momento = momento or timezone.now()
    tarjeta.status = GiftCardStatus.ACTIVE
    tarjeta.issued_at = momento
    tarjeta.expires_at = fecha_de_vencimiento(momento)
    tarjeta.balance = tarjeta.initial_amount
    tarjeta.save(update_fields=['status', 'issued_at', 'expires_at', 'balance', 'updated_at'])
    GiftCardMovement.objects.create(
        gift_card=tarjeta, kind=GiftCardMovementKind.ISSUE, amount=tarjeta.initial_amount,
        balance_after=tarjeta.balance, order=order, note='Pago de la compra aprobado.',
    )
    return tarjeta


def puede_retractarse(order):
    """Si la compra de una tarjeta se puede cancelar y devolver: la tarjeta no
    esta anulada y nunca se ha canjeado."""
    tarjeta = getattr(order, 'purchased_gift_card', None)
    return tarjeta is not None and tarjeta.status != GiftCardStatus.CANCELLED and tarjeta.is_unused


def anular_compra(order, nota, usuario=None):
    """Anula la tarjeta de una compra que se cancela (sin pago, o por retracto).
    El saldo que tuviera se pierde con ella: el dinero se devuelve por el
    medio de pago. No hace nada si ya estaba anulada."""
    tarjeta = GiftCard.objects.select_for_update().filter(purchase_order=order).first()
    if tarjeta is None or tarjeta.status == GiftCardStatus.CANCELLED:
        return tarjeta
    estaba_emitida = tarjeta.status != GiftCardStatus.PENDING
    saldo = tarjeta.balance
    tarjeta.status = GiftCardStatus.CANCELLED
    tarjeta.balance = CERO
    tarjeta.save(update_fields=['status', 'balance', 'updated_at'])
    if estaba_emitida and saldo > 0:
        GiftCardMovement.objects.create(
            gift_card=tarjeta, kind=GiftCardMovementKind.VOID, amount=-saldo, balance_after=CERO,
            order=order, note=nota[:255], created_by=_persona(usuario),
        )
    return tarjeta


def bloquear(tarjeta, motivo, usuario=None):
    """Impide canjear la tarjeta sin tocar su saldo (se puede desbloquear)."""
    tarjeta = GiftCard.objects.select_for_update().get(pk=tarjeta.pk)
    if tarjeta.status != GiftCardStatus.ACTIVE:
        return tarjeta
    tarjeta.status = GiftCardStatus.DISABLED
    tarjeta.disabled_reason = motivo[:255]
    tarjeta.save(update_fields=['status', 'disabled_reason', 'updated_at'])
    return tarjeta


def desbloquear(tarjeta):
    tarjeta = GiftCard.objects.select_for_update().get(pk=tarjeta.pk)
    if tarjeta.status != GiftCardStatus.DISABLED:
        return tarjeta
    tarjeta.status = GiftCardStatus.ACTIVE
    tarjeta.disabled_reason = ''
    tarjeta.save(update_fields=['status', 'disabled_reason', 'updated_at'])
    return tarjeta


# ---------------------------------------------------------------- canje

def canjear(tarjeta, order, por_pagar):
    """Descuenta del saldo lo que cubre del pedido (como maximo `por_pagar`) y
    devuelve ese monto. Se llama dentro de la transaccion que crea el pedido:
    si algo falla despues, el canje se revierte con ella.

    La tarjeta se relee bloqueada: dos compras simultaneas con la misma
    tarjeta no pueden gastar el mismo saldo."""
    tarjeta = GiftCard.objects.select_for_update().get(pk=tarjeta.pk)
    if not tarjeta.is_usable():
        raise TarjetaNoDisponible()
    monto = min(tarjeta.balance, Decimal(por_pagar)).quantize(Decimal('0.01'))
    if monto <= 0:
        return CERO
    tarjeta.balance -= monto
    tarjeta.save(update_fields=['balance', 'updated_at'])
    GiftCardMovement.objects.create(
        gift_card=tarjeta, kind=GiftCardMovementKind.REDEEM, amount=-monto,
        balance_after=tarjeta.balance, order=order, note=f'Pedido {order.order_number}.',
    )
    return monto


def saldo_tomado_por(order):
    """Lo que el pedido tiene tomado de su tarjeta ahora mismo (canjes menos
    devoluciones)."""
    neto = (
        GiftCardMovement.objects
        .filter(order=order, kind__in=[GiftCardMovementKind.REDEEM, GiftCardMovementKind.RELEASE])
        .aggregate(neto=Sum('amount'))['neto']
    )
    return -(neto or CERO)


def devolver_saldo(order, nota, usuario=None):
    """Devuelve a la tarjeta lo que un pedido cancelado o devuelto tomo de ella.
    Idempotente: si ya se devolvio, no hace nada. Devuelve el monto devuelto.

    El saldo vuelve aunque la tarjeta ya haya vencido o este bloqueada (es el
    medio con que se pago); en ese caso la nota del movimiento lo dice para
    que el equipo lo atienda."""
    if not order.gift_card_id:
        return CERO
    tarjeta = GiftCard.objects.select_for_update().get(pk=order.gift_card_id)
    monto = min(saldo_tomado_por(order), tarjeta.initial_amount - tarjeta.balance)
    if monto <= 0:
        return CERO
    tarjeta.balance += monto
    tarjeta.save(update_fields=['balance', 'updated_at'])
    if not tarjeta.is_usable():
        nota = f'{nota} La tarjeta no está disponible para canjear ({tarjeta.get_status_display()}'
        nota += ', vencida).' if tarjeta.is_expired() else ').'
    GiftCardMovement.objects.create(
        gift_card=tarjeta, kind=GiftCardMovementKind.RELEASE, amount=monto,
        balance_after=tarjeta.balance, order=order, note=nota[:255], created_by=_persona(usuario),
    )
    return monto


def _persona(usuario):
    return usuario if getattr(usuario, 'is_authenticated', False) else None


# ---------------------------------------------------------------- reportes

def saldo_vigente():
    """Saldo por canjear de las tarjetas activas y sin vencer: lo que la
    tienda debe en mercancia (un pasivo, no un ingreso). Las tarjetas de
    pedidos de prueba no cuentan: por ellas no entro dinero."""
    return (
        GiftCard.objects
        .filter(status=GiftCardStatus.ACTIVE, expires_at__gte=timezone.now())
        .exclude(purchase_order__is_test_order=True)
        .aggregate(total=Sum('balance'))['total'] or CERO
    )
