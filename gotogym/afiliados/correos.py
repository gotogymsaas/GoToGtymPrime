"""Correos del programa de afiliados.

Cada funcion es una tarea para `gotogym.tasks.enqueue`: vive a nivel de
modulo y recibe solo datos simples (ids y texto). Un fallo de correo nunca
debe deshacer la accion que lo origino, asi que se deja en el log.

Cada correo se escribe como contenido (`gotogym.correo`) y sale como HTML de
marca con su version de texto.
"""
import logging
from decimal import Decimal

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from gotogym.correo import Correo, aviso, boton, datos, enviar_correo, parrafo
from orders.models import CouponDiscountType
from tienda.templatetags.tienda_filters import cop

from .models import Commission, ConfiguracionProgramaAfiliados, PerfilAfiliado, RecursoMarca

logger = logging.getLogger(__name__)

KICKER = 'Programa de afiliados'
PIE = 'Recibes este correo porque participas en el programa de afiliados de GoToGym.'
ESCRIBENOS = 'Si tienes dudas, escríbenos a support@gotogym.store.'


def _enlace(nombre_de_ruta):
    return f'{settings.SITIO_URL}{reverse(nombre_de_ruta)}'


def _fecha(momento):
    return f'{timezone.localtime(momento):%d/%m/%Y}'


def _correo(usuario, asunto, titulo, bloques):
    return Correo(
        asunto=asunto, titulo=titulo, bloques=bloques,
        kicker=KICKER, saludo=_saludo(usuario), pie=PIE,
    )


def _enviar(usuario, correo):
    try:
        enviar_correo(usuario.email, correo)
    except Exception:
        logger.exception('No se pudo enviar el correo "%s" a %s', correo.asunto, usuario.pk)


def _perfil(perfil_id):
    return PerfilAfiliado.objects.select_related('user').get(pk=perfil_id)


def _saludo(usuario):
    return f'Hola {usuario.first_name or usuario.email},'


def _ir_al_panel(texto, frase_con_enlace=None):
    enlace = _enlace('afiliado_dashboard')
    return boton(texto, enlace, texto_plano=f'{frase_con_enlace}: {enlace}' if frase_con_enlace else None)


def solicitud_recibida(perfil_id):
    perfil = _perfil(perfil_id)
    _enviar(perfil.user, _correo(
        perfil.user, 'Recibimos tu solicitud al programa de afiliados de GoToGym', 'Recibimos tu solicitud', [
            parrafo(
                'Recibimos tu solicitud para ser afiliado de GoToGym. El equipo revisará tus datos y tus redes '
                'y te escribiremos cuando tengamos una respuesta.'
            ),
            _ir_al_panel('Ver el estado de mi solicitud', 'Puedes seguir el estado desde tu panel'),
        ],
    ))


def _porcentaje(valor):
    """10.00 -> "10"; 12.50 -> "12.5"."""
    return format(Decimal(valor).normalize(), 'f')


def _descuento_del_codigo(cupon):
    """Filas con lo que recibe quien compra con el codigo del afiliado."""
    if cupon.discount_type == CouponDiscountType.PERCENTAGE:
        descuento = f'{_porcentaje(cupon.value)} % de descuento'
    else:
        descuento = f'${cop(cupon.value)} COP de descuento'
    filas = [('Descuento para quien compra', descuento)]
    if cupon.min_purchase:
        filas.append(('Compra mínima', f'${cop(cupon.min_purchase)} COP'))
    if cupon.ends_at:
        filas.append(('Vigente hasta', _fecha(cupon.ends_at)))
    if cupon.max_uses:
        filas.append(('Usos máximos', str(cupon.max_uses)))
    return filas


def afiliado_aprobado(perfil_id):
    """Bienvenida al aprobarse: su codigo y enlace, el descuento que recibe quien
    compra con el codigo, lo que gana el afiliado y como empezar."""
    # Import diferido: `services` importa este modulo.
    from .services import DIAS_DE_VALIDACION, DIAS_HABILES_PARA_PAGAR, get_commission_rate

    perfil = _perfil(perfil_id)
    programa = ConfiguracionProgramaAfiliados.load()
    cupon = perfil.coupons.filter(is_active=True).order_by('id').first()
    enlace = f'{settings.SITIO_URL}{reverse("home")}?ref={perfil.referral_code}'

    bloques = [
        parrafo('Tu solicitud fue aprobada: ya haces parte del programa de afiliados de GoToGym. '
                'Estos son tus datos para empezar.'),
        datos([('Tu código', perfil.referral_code), ('Tu enlace para compartir', enlace)]),
    ]
    if cupon:
        bloques += [parrafo('Quien compre con tu código o tu enlace recibe:'), datos(_descuento_del_codigo(cupon))]
    bloques += [
        parrafo('Así ganas tú:'),
        datos([
            ('Comisión por venta', f'{_porcentaje(get_commission_rate(perfil))} % del subtotal del pedido'),
            ('Validación', f'{DIAS_DE_VALIDACION} días hábiles después de la entrega'),
            ('Mínimo para cobrar', f'${cop(programa.minimum_payout)} COP'),
            ('Pago', f'En los primeros {DIAS_HABILES_PARA_PAGAR} días hábiles del mes siguiente'),
        ]),
    ]
    pasos = [
        'Inscribe tu cuenta Bre-B en tu panel: sin ella no podemos pagarte.',
        'Comparte tu enlace o tu código con tu comunidad.',
        'Sigue tus ventas y tus comisiones desde el panel.',
    ]
    if RecursoMarca.objects.filter(is_active=True).exists():
        pasos.append('Descarga el material de marca en la sección Recursos del panel.')
    lista_de_pasos = '\n'.join(f'{numero}. {paso}' for numero, paso in enumerate(pasos, start=1))
    bloques += [
        parrafo(f'Para empezar:\n{lista_de_pasos}'),
        _ir_al_panel('Ir a mi panel'),
        aviso('Recuerda identificar como publicidad el contenido en el que uses tu código.'),
    ]
    _enviar(perfil.user, _correo(
        perfil.user, 'Te damos la bienvenida al programa de afiliados de GoToGym', 'Te damos la bienvenida', bloques,
    ))


def afiliado_rechazado(perfil_id):
    perfil = _perfil(perfil_id)
    bloques = [parrafo('Revisamos tu solicitud y, por ahora, no podemos aprobarla.')]
    if perfil.rejection_reason:
        bloques.append(aviso(f'Motivo: {perfil.rejection_reason}'))
    enlace = _enlace('afiliado_suscribete')
    bloques += [
        parrafo('Si crees que las condiciones cambiaron, puedes volver a postularte.'),
        boton('Volver a postularme', enlace, texto_plano=f'Puedes volver a postularte desde {enlace}.'),
    ]
    _enviar(perfil.user, _correo(
        perfil.user, 'Sobre tu solicitud al programa de afiliados de GoToGym', 'Sobre tu solicitud', bloques,
    ))


def baja_solicitada(perfil_id):
    perfil = _perfil(perfil_id)
    _enviar(perfil.user, _correo(
        perfil.user, 'Recibimos tu aviso de baja del programa de afiliados', 'Recibimos tu aviso de baja', [
            parrafo(
                f'Registramos tu aviso de baja el {_fecha(perfil.exit_requested_at)}. '
                f'Tu baja será efectiva el {_fecha(perfil.exit_effective_at)} (15 días después del aviso). '
                'Hasta esa fecha tu código y tu panel siguen activos.'
            ),
            parrafo(
                'Las comisiones que hayas confirmado por encima del mínimo de pago se liquidan en el siguiente '
                'ciclo de pagos. Si cambias de opinión, puedes cancelar la baja desde tu panel.'
            ),
            _ir_al_panel('Ir a mi panel', 'Panel'),
        ],
    ))


def baja_efectiva(perfil_id):
    perfil = _perfil(perfil_id)
    _enviar(perfil.user, _correo(
        perfil.user, 'Tu baja del programa de afiliados ya es efectiva', 'Tu baja ya es efectiva', [
            parrafo(
                'Tu baja del programa de afiliados de GoToGym ya es efectiva: dejamos de rastrear compras con tu '
                'código. Puedes seguir entrando a tu panel para ver y solicitar el pago de tus comisiones confirmadas.'
            ),
            _ir_al_panel('Ir a mi panel', 'Panel'),
        ],
    ))


def terminacion(perfil_id):
    perfil = _perfil(perfil_id)
    motivo = perfil.get_exit_reason_display()
    notas = f'\n{perfil.exit_notes}' if perfil.exit_notes else ''
    _enviar(perfil.user, _correo(
        perfil.user, 'Terminamos tu participación en el programa de afiliados', 'Terminamos tu participación', [
            parrafo(
                'Terminamos tu participación en el programa de afiliados de GoToGym y desactivamos tu código.'
            ),
            aviso(f'Motivo: {motivo}.{notas}'),
            parrafo(
                'Las comisiones válidas y confirmadas que superen el mínimo se pagan en el siguiente ciclo; '
                'las asociadas a ventas fraudulentas o que incumplen los términos se invalidan. '
                'Si tienes dudas, escríbenos a support@gotogym.store.'
            ),
        ],
    ))


def validacion_extendida(comision_id):
    comision = Commission.objects.select_related('afiliado__user', 'order').get(pk=comision_id)
    usuario = comision.afiliado.user
    _enviar(usuario, _correo(
        usuario, 'Extendimos el periodo de validación de una comisión', 'Extendimos la validación de una comisión', [
            parrafo(
                f'Extendimos el periodo de validación de tu comisión del pedido {comision.order.order_number} '
                f'hasta el {comision.validation_last_day:%d/%m/%Y}.'
            ),
            aviso(f'Motivo: {comision.extension_reason}'),
            parrafo(f'Mientras tanto la comisión sigue como pendiente en tu panel. {ESCRIBENOS}'),
        ],
    ))


def cambio_de_tasa(perfil_id, tasa):
    perfil = _perfil(perfil_id)
    _enviar(perfil.user, _correo(
        perfil.user, 'Cambio en tu comisión del programa de afiliados', 'Cambio en tu comisión', [
            parrafo(
                f'La comisión por tus ventas pasa a ser del {tasa} %. El cambio aplica a las compras que se hagan '
                'con tu código a partir de hoy; las comisiones ya registradas conservan la tasa con la que se '
                'calcularon.'
            ),
            parrafo('Si no estás de acuerdo, puedes darte de baja sin penalización desde tu panel.'),
        ],
    ))


def aviso_general(perfil_id, asunto, mensaje):
    perfil = _perfil(perfil_id)
    _enviar(perfil.user, _correo(perfil.user, asunto, asunto, [parrafo(mensaje)]))
