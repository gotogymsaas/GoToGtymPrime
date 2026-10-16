"""Limitador de tasa: bloquea tras superar el limite, aisla por cliente."""
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase
from django.test.utils import override_settings

from .ratelimit import ip_del_cliente, rate_limit


class _AnonUser:
    is_authenticated = False


class _RealUser:
    is_authenticated = True

    def __init__(self, pk):
        self.pk = pk


@override_settings(
    RATE_LIMIT_ENABLED=True,
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}},
)
class RateLimitTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def _request(self, user=None, ip='10.0.0.1'):
        request = self.factory.post('/algun-endpoint/')
        request.user = user or _AnonUser()
        request.META['REMOTE_ADDR'] = ip
        return request

    def test_permite_hasta_el_limite(self):
        vista = rate_limit('test-a', limit=3, period_seconds=60)(lambda r: HttpResponse('ok'))
        request = self._request()
        for _ in range(3):
            response = vista(request)
            self.assertEqual(response.status_code, 200)

    def test_bloquea_al_superar_el_limite(self):
        vista = rate_limit('test-b', limit=2, period_seconds=60)(lambda r: HttpResponse('ok'))
        request = self._request()
        vista(request)
        vista(request)
        response = vista(request)
        self.assertEqual(response.status_code, 429)

    def test_clientes_distintos_no_se_afectan_entre_si(self):
        vista = rate_limit('test-c', limit=1, period_seconds=60)(lambda r: HttpResponse('ok'))

        request_a = self._request(user=_RealUser(pk=1))
        request_b = self._request(user=_RealUser(pk=2))

        self.assertEqual(vista(request_a).status_code, 200)
        self.assertEqual(vista(request_a).status_code, 429)
        # Otro usuario no deberia verse afectado por el limite del primero.
        self.assertEqual(vista(request_b).status_code, 200)

    def test_usuarios_anonimos_se_distinguen_por_ip(self):
        vista = rate_limit('test-d', limit=1, period_seconds=60)(lambda r: HttpResponse('ok'))

        request_ip1 = self._request(ip='10.0.0.1')
        request_ip2 = self._request(ip='10.0.0.2')

        self.assertEqual(vista(request_ip1).status_code, 200)
        self.assertEqual(vista(request_ip1).status_code, 429)
        self.assertEqual(vista(request_ip2).status_code, 200)

    def test_distintos_key_prefix_no_comparten_limite(self):
        vista_a = rate_limit('test-e-a', limit=1, period_seconds=60)(lambda r: HttpResponse('ok'))
        vista_b = rate_limit('test-e-b', limit=1, period_seconds=60)(lambda r: HttpResponse('ok'))
        request = self._request()

        self.assertEqual(vista_a(request).status_code, 200)
        # Un endpoint distinto no deberia consumir el mismo contador.
        self.assertEqual(vista_b(request).status_code, 200)

    def test_la_ventana_es_fija_y_no_se_prolonga_con_cada_peticion(self):
        # Con la versión anterior cada petición renovaba el vencimiento: quien
        # insistía cada pocos segundos nunca recuperaba el acceso.
        from unittest.mock import patch

        vista = rate_limit('test-ventana', limit=1, period_seconds=60)(lambda r: HttpResponse('ok'))
        with patch.object(cache, 'set', wraps=cache.set) as set_cache:
            vista(self._request())
            vista(self._request())
            vista(self._request())
        set_cache.assert_not_called()  # el vencimiento lo fija solo el primer `add`

    def test_si_la_clave_caduca_entre_dos_pasos_empieza_otra_ventana(self):
        from unittest.mock import patch

        vista = rate_limit('test-caduca', limit=1, period_seconds=60)(lambda r: HttpResponse('ok'))
        with patch.object(cache, 'incr', side_effect=ValueError('Key not found')):
            self.assertEqual(vista(self._request()).status_code, 200)


    def test_solo_cuenta_los_metodos_indicados(self):
        vista = rate_limit('test-metodos', limit=1, period_seconds=60, metodos=('POST',))(lambda r: HttpResponse('ok'))
        consulta = self.factory.get('/formulario/')
        consulta.user = _AnonUser()
        consulta.META['REMOTE_ADDR'] = '10.0.0.1'
        for _ in range(5):
            self.assertEqual(vista(consulta).status_code, 200)
        self.assertEqual(vista(self._request()).status_code, 200)
        self.assertEqual(vista(self._request()).status_code, 429)

    @override_settings(RATE_LIMIT_ENABLED=False)
    def test_apagado_no_limita(self):
        vista = rate_limit('test-apagado', limit=1, period_seconds=60)(lambda r: HttpResponse('ok'))
        for _ in range(5):
            self.assertEqual(vista(self._request()).status_code, 200)


@override_settings(TRUSTED_PROXY_HOPS=1)
class IpDelClienteTests(SimpleTestCase):
    """Detras del proxy de Azure la conexion siempre llega desde el proxy: la
    IP del cliente es la que el proxy agrego a X-Forwarded-For."""

    def _peticion(self, reenviadas=None, remoto='169.254.130.1'):
        peticion = RequestFactory().get('/')
        peticion.META['REMOTE_ADDR'] = remoto
        if reenviadas is not None:
            peticion.META['HTTP_X_FORWARDED_FOR'] = reenviadas
        return peticion

    def test_usa_la_ip_que_agrego_el_proxy_y_quita_el_puerto(self):
        self.assertEqual(ip_del_cliente(self._peticion('200.1.2.3:51234')), '200.1.2.3')

    def test_ignora_lo_que_el_cliente_pudo_inventar_antes(self):
        self.assertEqual(ip_del_cliente(self._peticion('9.9.9.9, 200.1.2.3:51234')), '200.1.2.3')

    def test_ipv6_con_puerto(self):
        self.assertEqual(ip_del_cliente(self._peticion('[2800:484::1]:443')), '2800:484::1')

    def test_sin_cabecera_usa_la_conexion(self):
        self.assertEqual(ip_del_cliente(self._peticion()), '169.254.130.1')

    @override_settings(TRUSTED_PROXY_HOPS=0)
    def test_sin_proxies_de_confianza_ignora_la_cabecera(self):
        self.assertEqual(ip_del_cliente(self._peticion('9.9.9.9', remoto='10.0.0.7')), '10.0.0.7')
