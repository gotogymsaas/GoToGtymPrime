"""Captura del enlace de referido (`?ref=<codigo>`).

Complementa al codigo tecleado a mano en el checkout (P08, referencia dual):
quien llega por un enlace compartido por un afiliado no tiene que copiar
nada, y ademas queda contado como clic (metrica A6) sin depender de que
complete una compra."""

from orders.models import Coupon

from .models import ReferralClick

REFERRAL_QUERY_PARAM = 'ref'
SESSION_CODE_KEY = 'referral_code'
SESSION_COUNTED_KEY = 'referral_clicks_counted'


class ReferralTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        codigo = (request.GET.get(REFERRAL_QUERY_PARAM) or '').strip().upper()
        if codigo:
            self._registrar(request, codigo)
        return self.get_response(request)

    def _registrar(self, request, codigo):
        cupon = (
            Coupon.objects
            .filter(code=codigo, is_active=True, influencer__isnull=False)
            .select_related('influencer')
            .first()
        )
        if cupon is None:
            return

        contados = request.session.get(SESSION_COUNTED_KEY, [])
        if codigo not in contados:
            ReferralClick.objects.create(influencer=cupon.influencer)
            contados.append(codigo)
            request.session[SESSION_COUNTED_KEY] = contados

        request.session[SESSION_CODE_KEY] = codigo
