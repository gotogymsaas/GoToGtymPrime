"""Limitador de tasa: bloquea tras superar el limite, aisla por cliente."""
from datetime import UTC
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.test.utils import override_settings

from .ratelimit import contar, ip_del_cliente, olvidar, rate_limit


class _AnonUser:
    is_authenticated = False


class _RealUser:
    is_authenticated = True

    def __init__(self, pk):
        self.pk = pk


class _Reloj:
    """Reloj controlable: el limitador cuenta por ventanas de reloj y una
    prueba que cruzara el cambio de minuto se partiria en dos."""

    def __init__(self, ahora=1_000_020.0):  # multiplo de 60
        self.ahora = ahora

    def __call__(self):
        return self.ahora

    def avanzar(self, segundos):
        self.ahora += segundos


class _PruebasDelLimitador:
    """Se ejecutan sobre cada backend de cache: el limitador tiene que
    comportarse igual en memoria local, en tabla y en Redis."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)
        self.factory = RequestFactory()
        self.reloj = _Reloj()
        parche = mock.patch('gotogym.ratelimit._ahora', self.reloj)
        parche.start()
        self.addCleanup(parche.stop)

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

    def test_la_ventana_termina_a_los_segundos_indicados(self):
        vista = rate_limit('test-ventana', limit=2, period_seconds=60)(lambda r: HttpResponse('ok'))
        self.assertEqual(vista(self._request()).status_code, 200)
        self.assertEqual(vista(self._request()).status_code, 200)
        self.assertEqual(vista(self._request()).status_code, 429)

        self.reloj.avanzar(60)

        self.assertEqual(vista(self._request()).status_code, 200)

    def test_insistir_no_prolonga_la_ventana(self):
        # Quien sigue enviando dentro de la ventana no debe quedar bloqueado
        # mas alla de ella, aunque el backend renueve el vencimiento al escribir.
        vista = rate_limit('test-insiste', limit=1, period_seconds=60)(lambda r: HttpResponse('ok'))
        self.assertEqual(vista(self._request()).status_code, 200)
        for _ in range(5):
            self.reloj.avanzar(10)
            self.assertEqual(vista(self._request()).status_code, 429)

        self.reloj.avanzar(10)

        self.assertEqual(vista(self._request()).status_code, 200)

    def test_contar_devuelve_el_total_de_la_ventana(self):
        self.assertEqual([contar('c', 60) for _ in range(3)], [1, 2, 3])
        self.reloj.avanzar(60)
        self.assertEqual(contar('c', 60), 1)

    def test_olvidar_pone_a_cero_la_ventana_actual(self):
        contar('o', 60)
        contar('o', 60)
        olvidar('o', 60)
        self.assertEqual(contar('o', 60), 1)

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


_LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
_EN_TABLA = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'cache_del_limitador',
        'TIMEOUT': 300,
    },
}


@override_settings(RATE_LIMIT_ENABLED=True, CACHES=_LOCMEM)
class RateLimitTests(_PruebasDelLimitador, SimpleTestCase):
    pass


@override_settings(RATE_LIMIT_ENABLED=True, CACHES=_EN_TABLA)
class RateLimitCacheEnTablaTests(_PruebasDelLimitador, TestCase):
    """Produccion sin Redis usa la cache en tabla, cuyo `incr` reescribe la
    clave con el vencimiento por defecto en vez del de la ventana."""

    def setUp(self):
        call_command('createcachetable', verbosity=0)
        super().setUp()

    def _vence_en(self, clave_base, periodo):
        from django.db import connection

        from .ratelimit import _clave_de_ventana
        clave = cache.make_key(_clave_de_ventana(clave_base, periodo))
        with connection.cursor() as cursor:
            cursor.execute('SELECT expires FROM cache_del_limitador WHERE cache_key = %s', [clave])
            return cursor.fetchone()[0]

    def test_un_tope_largo_conserva_su_vencimiento_al_seguir_contando(self):
        from datetime import datetime, timedelta

        contar('tope-dia', 86400)
        contar('tope-dia', 86400)
        contar('tope-dia', 86400)

        vence = self._vence_en('tope-dia', 86400)
        if isinstance(vence, str):
            vence = datetime.fromisoformat(vence)
        if vence.tzinfo is None:
            vence = vence.replace(tzinfo=UTC)
        restante = vence - datetime.now(UTC)
        # Con la cache en tabla y `incr` quedaria en 300 s.
        self.assertGreater(restante, timedelta(hours=23))


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
