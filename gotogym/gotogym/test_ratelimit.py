"""Limitador de tasa: bloquea tras superar el limite, aisla por cliente."""
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase
from django.test.utils import override_settings

from .ratelimit import rate_limit


class _AnonUser:
    is_authenticated = False


class _RealUser:
    is_authenticated = True

    def __init__(self, pk):
        self.pk = pk


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
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
