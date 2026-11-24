"""Las rutas de subida del Coach (foto, archivo y voz) estan marcadas con
`csrf_exempt` y vuelven a exigir el token con `csrf_protect` dentro de la
vista, para cambiar antes el manejador de subida. Estas pruebas comprueban,
con la verificacion CSRF activa, que esa excepcion no deja la ruta abierta:
sin token (o con uno falso) la peticion se rechaza con 403 antes de leer el
archivo, y con un token valido llega a la logica de la vista."""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

# (nombre de la ruta, campo del archivo, codigo de error propio de la vista)
RUTAS = (
    ('vendedor:imagen', 'imagen', 'imagen_invalida'),
    ('vendedor:documento', 'documento', 'documento_invalido'),
    ('vendedor:voz', 'audio', 'voz_invalida'),
)


@override_settings(VENDEDOR_ENABLED=True, VENDEDOR_ROLLOUT_PERCENT=100, VENDEDOR_IMAGEN_ACCESO='todos')
class SubidasExigenCsrfTests(TestCase):
    def setUp(self):
        self.cliente = Client(enforce_csrf_checks=True)
        # La portada pone la cookie del token (la usa el formulario de analitica).
        self.cliente.get('/es/')
        self.token = self.cliente.cookies['csrftoken'].value

    def _enviar(self, ruta, campo, con_archivo=True, **extra):
        datos = {'message': 'hola'}
        if con_archivo:
            datos[campo] = SimpleUploadedFile(f'{campo}.bin', b'contenido', content_type='application/octet-stream')
        return self.cliente.post(reverse(ruta), datos, **extra)

    def test_sin_token_se_rechaza_con_403(self):
        for ruta, campo, _codigo in RUTAS:
            with self.subTest(ruta=ruta):
                self.assertEqual(self._enviar(ruta, campo).status_code, 403)

    def test_con_un_token_falso_se_rechaza_con_403(self):
        for ruta, campo, _codigo in RUTAS:
            with self.subTest(ruta=ruta):
                respuesta = self._enviar(ruta, campo, HTTP_X_CSRFTOKEN='a' * 64)
                self.assertEqual(respuesta.status_code, 403)

    def test_sin_token_tampoco_llega_a_la_logica_aunque_falte_el_archivo(self):
        for ruta, campo, _codigo in RUTAS:
            with self.subTest(ruta=ruta):
                respuesta = self._enviar(ruta, campo, con_archivo=False)
                self.assertEqual(respuesta.status_code, 403)
                # La pagina de error del sitio, no el JSON de error propio de la vista.
                self.assertNotIn('application/json', respuesta['Content-Type'])

    def test_con_token_valido_llega_a_la_logica_de_la_vista(self):
        # Sin archivo, la propia vista responde 400 con su codigo de error: la
        # prueba de que paso el CSRF y se ejecuto el codigo de la ruta.
        for ruta, campo, codigo in RUTAS:
            with self.subTest(ruta=ruta):
                respuesta = self._enviar(ruta, campo, con_archivo=False, HTTP_X_CSRFTOKEN=self.token)
                self.assertEqual(respuesta.status_code, 400)
                self.assertEqual(respuesta.json()['error'], codigo)

    def test_con_token_valido_y_archivo_no_es_un_rechazo_de_csrf(self):
        for ruta, campo, _codigo in RUTAS:
            with self.subTest(ruta=ruta):
                respuesta = self._enviar(ruta, campo, HTTP_X_CSRFTOKEN=self.token)
                self.assertNotEqual(respuesta.status_code, 403)

    def test_el_token_tambien_vale_enviado_como_campo_del_formulario(self):
        for ruta, _campo, codigo in RUTAS:
            with self.subTest(ruta=ruta):
                respuesta = self.cliente.post(reverse(ruta), {'csrfmiddlewaretoken': self.token, 'message': 'hola'})
                self.assertEqual(respuesta.json()['error'], codigo)

    def test_una_ruta_oculta_responde_404_y_no_filtra_nada_antes_del_csrf(self):
        # Foto solo para el equipo: un visitante no distingue la ruta de una que no existe.
        with override_settings(VENDEDOR_IMAGEN_ACCESO='staff'):
            self.assertEqual(self._enviar('vendedor:imagen', 'imagen').status_code, 404)

    def test_un_usuario_autenticado_tampoco_se_salta_la_verificacion(self):
        usuario = get_user_model().objects.create_user('csrf-subidas@example.com', 'x', 'csrf-subidas')
        self.cliente.force_login(usuario)
        for ruta, campo, _codigo in RUTAS:
            with self.subTest(ruta=ruta):
                self.assertEqual(self._enviar(ruta, campo).status_code, 403)
