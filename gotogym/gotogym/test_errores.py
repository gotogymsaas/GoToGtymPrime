"""Paginas de error por codigo y registro en logs/errores.txt."""
import logging
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import BadRequest, PermissionDenied
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import path
from django.utils import translation
from django.views.decorators.http import require_POST

from . import urls as urls_del_sitio
from .registro_errores import configuracion_logging, referencia_de


def _explota(request):
    raise RuntimeError('fallo de prueba')


@require_POST
def _solo_post(request):
    return HttpResponse('ok')


def _prohibido(request):
    raise PermissionDenied


def _mal_pedido(request):
    raise BadRequest


def _limitada(request):
    return HttpResponse('Demasiadas solicitudes.', status=429)


urlpatterns = urls_del_sitio.urlpatterns + [
    path('prueba/explota/', _explota),
    path('prueba/solo-post/', _solo_post),
    path('prueba/prohibido/', _prohibido),
    path('prueba/mal-pedido/', _mal_pedido),
    path('prueba/limitada/', _limitada),
]
handler400 = urls_del_sitio.handler400
handler403 = urls_del_sitio.handler403
handler404 = urls_del_sitio.handler404
handler500 = urls_del_sitio.handler500


def _leer_log():
    for manejador in logging.getLogger().handlers:
        manejador.flush()
    ruta = Path(settings.LOGGING['handlers']['archivo_errores']['filename'])
    return ruta.read_text(encoding='utf-8')


@override_settings(ROOT_URLCONF='gotogym.test_errores')
class PaginasDeErrorTests(TestCase):
    def setUp(self):
        # Una excepcion no controlada se relanza en el cliente de pruebas salvo
        # que se le pida devolver la respuesta 500 real.
        self.cliente = Client(raise_request_exception=False)

    def tearDown(self):
        translation.activate('es')

    def test_404_muestra_su_pagina(self):
        r = self.cliente.get('/es/no-existe-esta-ruta/')
        self.assertContains(r, 'Página no encontrada', status_code=404)
        self.assertContains(r, 'Error 404', status_code=404)
        self.assertContains(r, 'gtg-navbar', status_code=404)

    def test_403_muestra_su_pagina(self):
        r = self.cliente.get('/prueba/prohibido/')
        self.assertContains(r, 'Acceso denegado', status_code=403)

    def test_400_muestra_su_pagina(self):
        r = self.cliente.get('/prueba/mal-pedido/')
        self.assertContains(r, 'Solicitud no válida', status_code=400)

    def test_500_muestra_la_pagina_autonoma_con_referencia(self):
        r = self.cliente.get('/prueba/explota/')
        self.assertContains(r, 'Algo salió mal', status_code=500)
        self.assertNotContains(r, 'gtg-navbar', status_code=500)
        self.assertRegex(r.content.decode(), r'Referencia: <strong>[0-9A-F]{8}</strong>')

    def test_405_muestra_su_pagina_y_conserva_allow(self):
        r = self.cliente.get('/prueba/solo-post/')
        self.assertContains(r, 'Acción no permitida', status_code=405)
        self.assertEqual(r['Allow'], 'POST')

    def test_429_muestra_su_pagina(self):
        r = self.cliente.get('/prueba/limitada/')
        self.assertContains(r, 'Demasiadas solicitudes', status_code=429)
        self.assertContains(r, 'Error 429', status_code=429)

    def test_405_y_429_conservan_la_respuesta_para_ajax(self):
        r = self.cliente.get('/prueba/limitada/', HTTP_ACCEPT='application/json')
        self.assertEqual(r.content, b'Demasiadas solicitudes.')
        r = self.cliente.get('/prueba/solo-post/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 405)
        self.assertNotIn(b'Error 405', r.content)

    def test_el_webhook_no_se_reemplaza(self):
        r = self.cliente.get('/pagos/webhook/mercadopago/')
        self.assertEqual(r.status_code, 405)
        self.assertNotIn(b'Error 405', r.content)

    def test_readiness_confirma_la_base_de_datos(self):
        r = self.cliente.get('/readyz')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {'status': 'ready', 'database': 'available'})

    def test_fallo_csrf_muestra_403_y_se_registra(self):
        cliente = Client(enforce_csrf_checks=True)
        r = cliente.post('/es/accounts/acceso/', {'username': 'a', 'password': 'b'})
        self.assertContains(r, 'Acceso denegado', status_code=403)
        self.assertIn('Forbidden (CSRF cookie not set.): /es/accounts/acceso/', _leer_log())

    def test_las_paginas_salen_en_el_idioma_de_la_url(self):
        self.assertContains(self.cliente.get('/en/no-existe/'), 'Page not found', status_code=404)
        self.assertContains(self.cliente.get('/pt/nao-existe/'), 'Página não encontrada', status_code=404)

    def test_el_404_funciona_con_sesion_iniciada(self):
        usuario = get_user_model().objects.create_user(
            username='u', email='u@example.com', password='Clave-segura-123')
        self.cliente.force_login(usuario)
        self.assertContains(self.cliente.get('/es/no-existe/'), 'Error 404', status_code=404)


@override_settings(ROOT_URLCONF='gotogym.test_errores')
class RegistroDeErroresTests(TestCase):
    def setUp(self):
        self.cliente = Client(raise_request_exception=False)

    def test_un_404_queda_en_el_archivo_con_su_contexto(self):
        self.cliente.get('/es/ruta-inexistente-log/?token=secreto', REMOTE_ADDR='203.0.113.7')
        linea = next(li for li in _leer_log().splitlines() if '/es/ruta-inexistente-log/' in li)
        self.assertIn('WARNING', linea)
        self.assertIn('| 404 |', linea)
        self.assertIn('ip=203.0.113.7', linea)
        self.assertIn('usuario=anonimo', linea)
        self.assertIn('GET /es/ruta-inexistente-log/', linea)
        self.assertNotIn('secreto', linea)

    def test_un_500_guarda_el_traceback_y_la_referencia_mostrada(self):
        r = self.cliente.get('/prueba/explota/')
        referencia = r.content.decode().split('<strong>')[1].split('</strong>')[0]
        log = _leer_log()
        inicio = log.rindex(f'ref={referencia}')
        bloque = log[log.rfind('\n', 0, inicio) + 1:]
        primera = bloque.splitlines()[0]
        self.assertIn('ERROR', primera)
        self.assertIn('| 500 |', primera)
        self.assertIn('Traceback (most recent call last)', bloque)
        self.assertIn('RuntimeError: fallo de prueba', bloque)

    def test_se_guarda_el_id_del_usuario_y_no_su_correo(self):
        usuario = get_user_model().objects.create_user(
            username='u2', email='privado@example.com', password='Clave-segura-123')
        self.cliente.force_login(usuario)
        self.cliente.get('/es/ruta-con-usuario/')
        linea = next(li for li in _leer_log().splitlines() if '/es/ruta-con-usuario/' in li)
        self.assertIn(f'usuario={usuario.pk} ', linea)
        self.assertNotIn('privado@example.com', linea)

    def test_los_errores_de_las_apps_tambien_se_guardan(self):
        logging.getLogger('payments.views').error('webhook rechazado de prueba')
        linea = next(li for li in _leer_log().splitlines() if 'webhook rechazado de prueba' in li)
        self.assertIn('payments.views', linea)
        self.assertIn('ref=- | ip=-', linea)

    def test_la_referencia_es_estable_dentro_de_una_peticion(self):
        request = RequestFactory().get('/')
        self.assertEqual(referencia_de(request), referencia_de(request))

    def test_si_no_se_puede_escribir_el_servidor_sigue_arrancando(self):
        archivo = Path(settings.LOG_DIR) / 'no-es-un-directorio'
        archivo.write_text('x', encoding='utf-8')
        self.addCleanup(archivo.unlink)
        config = configuracion_logging(archivo / 'logs')
        self.assertNotIn('handlers', config)


@override_settings(ROOT_URLCONF='gotogym.test_errores', DEBUG=True, REEMPLAZAR_PAGINAS_DE_DEBUG=True)
class PaginasDeErrorConDebugTests(TestCase):
    """En desarrollo (DEBUG activo) Django ignora handler404/500 y muestra su
    pagina tecnica; el middleware la cambia por las del sitio."""

    def setUp(self):
        self.cliente = Client(raise_request_exception=False)

    def test_el_404_es_el_del_sitio_y_no_el_de_django(self):
        r = self.cliente.get('/es/no-existe/')
        self.assertContains(r, 'Error 404', status_code=404)
        self.assertNotContains(r, 'Django tried these URL patterns', status_code=404)

    def test_el_500_es_el_del_sitio_y_no_el_de_django(self):
        r = self.cliente.get('/prueba/explota/')
        self.assertContains(r, 'Algo salió mal', status_code=500)
        self.assertNotContains(r, 'RuntimeError', status_code=500)

    def test_el_traceback_sigue_en_el_log(self):
        r = self.cliente.get('/prueba/explota/')
        referencia = r.content.decode().split('<strong>')[1].split('</strong>')[0]
        log = _leer_log()
        self.assertIn(f'ref={referencia}', log)
        self.assertIn('RuntimeError: fallo de prueba', log)

    @override_settings(REEMPLAZAR_PAGINAS_DE_DEBUG=False)
    def test_sin_el_interruptor_sale_la_pagina_de_django(self):
        r = self.cliente.get('/prueba/explota/')
        self.assertContains(r, 'RuntimeError', status_code=500)
