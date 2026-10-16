"""Con el idioma en ingles, TODA la pagina sale en ingles.

Recorre las paginas de cara al cliente en `/en/` y falla si encuentra texto en
espanol. Los nombres propios (departamentos de Colombia, el idioma "Español" del
selector) estan permitidos. Si agregas texto nuevo a una plantilla, envuelvelo
en `{% trans %}` y agrega su traduccion en `locale/en/LC_MESSAGES/django.po`.
"""
import re
from decimal import Decimal
from html.parser import HTMLParser

from blog.models import Post
from carrito.services import write_cart
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import translation
from inventory.models import Inventory
from orders.services import create_order_from_cart
from products.models import Brand, Product, ProductCategory, ProductVariant

PERMITIDO = re.compile(
    r'Español|Bogotá|Medellín|Atlántico|Bolívar|Boyacá|Caquetá|Chocó|Córdoba|Guainía|Nariño|Quindío|Vaupés|'
    r'San Andrés y Providencia|Guatapé|Inírida|Maní|Bogota D\.C\.|Friends N Gifts|Banco de la República'
)
ACENTOS = re.compile(r'[áéíóúñ¿¡ÁÉÍÓÚÑ]')
# Palabras que en ingles no existen: dos o mas en un mismo texto delatan espanol.
SOLO_ESPANOL = set('para con una los las tu tus del que por como esta este estos sus nuestra nuestro puedes tienes'.split())
# Palabras de interfaz que en ingles no existen: una sola basta (aunque no lleven acento).
ESPANOL_SUELTO = set(
    'disponibles disponible agotado carrito tienda compra compras precio talla tallas pedido pedidos gracias guardar cancelar '
    'eliminar cantidad descuento siguiente anterior nombre apellido correo teléfono telefono ciudad dirección direccion '
    'contraseña contrasena ayuda inicio salir entrar buscar enviar continuar comisión comision afiliado afiliados solicitud '
    'pagos cuenta fecha detalle estado perfil envío envio unidades'.split()
)
OMITIR = {'script', 'style', 'noscript', 'svg', 'head', 'title'}

DATOS = {
    'first_name': 'Ana', 'last_name': 'Marin', 'email': 'ana-en@example.com', 'phone': '3001234567',
    'country': 'Colombia', 'department': 'Antioquia', 'city': 'Medellín', 'address_line': 'Calle 10 # 20-30',
}


class _Texto(HTMLParser):
    def __init__(self):
        super().__init__()
        self.pila, self.textos = [], []

    def handle_starttag(self, tag, attrs):
        if tag in OMITIR:
            self.pila.append(tag)
        for clave, valor in attrs:
            if clave in ('placeholder', 'aria-label', 'title', 'alt') and valor:
                self.textos.append(valor)

    def handle_endtag(self, tag):
        if self.pila and self.pila[-1] == tag:
            self.pila.pop()

    def handle_data(self, data):
        if not self.pila and data.strip():
            self.textos.append(re.sub(r'\s+', ' ', data).strip())


def en_espanol(texto):
    # Las rutas (/pedidos-tienda/...) llevan palabras en espanol sin ser texto visible.
    texto = re.sub(r'https?://\S+|(?<!\w)/[\w/.-]+', '', texto)
    texto = PERMITIDO.sub('', texto)
    if ACENTOS.search(texto):
        return True
    palabras = re.findall(r'[a-z]+', texto.lower())
    if any(p in ESPANOL_SUELTO for p in palabras):
        return True
    return sum(1 for p in palabras if p in SOLO_ESPANOL) >= 2


def textos_en_espanol(html):
    analizador = _Texto()
    analizador.feed(html)
    return [t for t in dict.fromkeys(analizador.textos) if en_espanol(t)]


class InglesCompletoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Las migraciones ya siembran categorias y marcas del catalogo.
        categoria, _ = ProductCategory.objects.get_or_create(name='Semi Personalizada')
        marca, _ = Brand.objects.get_or_create(name='GoToGym')
        cls.producto = Product.objects.create(
            name='Pantalon verde', category=categoria, brand=marca, base_price=Decimal('120000.0000'), stock=0,
            description='Pantalon verde para caballero, talla unica, en licra.',
        )
        cls.variante = ProductVariant.objects.create(product=cls.producto, sku='EN-001-U-VER', size='UNICA', color='verde')
        Inventory.objects.create(variant=cls.variante, quantity_available=20)
        cls.cliente = get_user_model().objects.create_user(
            email='ana-en@example.com', username='ana-en@example.com', password='Clave-Segura-123', first_name='Ana',
        )
        autor = get_user_model().objects.create_user(email='autor@example.com', username='autor@example.com', password='x')
        from blog.journal_content import POSTS
        for datos in POSTS:
            from blog.models import Category
            categoria_blog, _ = Category.objects.get_or_create(name=datos['category'])
            Post.objects.create(
                slug=datos['slug'], title=datos['title'], author=autor, category=categoria_blog,
                excerpt=datos['excerpt'], content=datos['content'], references=datos['references'],
            )

    def setUp(self):
        self.client.cookies['gtg_cookies'] = 'necesarias'
        translation.activate('en')

    def tearDown(self):
        translation.activate('es')

    def _ver(self, ruta, esperado=200):
        respuesta = self.client.get(ruta)
        self.assertEqual(respuesta.status_code, esperado, ruta)
        sobrantes = textos_en_espanol(respuesta.content.decode())
        self.assertEqual(sobrantes, [], f'{ruta}: texto en español con el sitio en inglés')
        return respuesta

    def _con_carrito(self):
        sesion = self.client.session
        write_cart(sesion, {str(self.variante.pk): 2})
        sesion.save()

    # --- visitante -------------------------------------------------------
    def test_paginas_publicas(self):
        for ruta in (
            '/en/', '/en/acerca-de/', '/en/contacto/', '/en/tienda/', f'/en/tienda/producto/{self.producto.pk}/',
            '/en/blog/', '/en/carrito/', '/en/accounts/acceso/', '/en/accounts/register/',
            '/en/accounts/password_reset/', '/en/afiliados/terminos/',
        ):
            with self.subTest(ruta=ruta):
                self._ver(ruta)

    def test_politicas_y_terminos(self):
        for nombre in (
            'politica_privacidad', 'terminos', 'politica_cambios', 'politica_devoluciones', 'politica_garantia',
            'politica_envios', 'politica_pagos', 'politica_tratamiento_datos', 'politica_cookies',
        ):
            with self.subTest(politica=nombre):
                with translation.override('en'):
                    ruta = reverse(nombre)
                self.assertTrue(ruta.startswith('/en/'))
                self._ver(ruta)

    def test_entradas_del_journal(self):
        for post in Post.objects.all():
            with self.subTest(post=post.slug):
                respuesta = self._ver(f'/en/blog/{post.slug}/')
                self.assertNotContains(respuesta, post.title)

    def test_busqueda_y_filtros_de_la_tienda(self):
        self._ver('/en/tienda/?filtro=pants&talla=UNICA&color=verde')
        self._ver('/en/tienda/?filtro=zzz')

    def test_carrito_con_productos(self):
        self._con_carrito()
        self._ver('/en/carrito/')

    # --- formularios y mensajes -----------------------------------------------
    def test_errores_de_acceso_y_registro(self):
        respuesta = self.client.post('/en/accounts/acceso/', {'username': 'x@example.com', 'password': 'mala'})
        self.assertEqual(textos_en_espanol(respuesta.content.decode()), [])
        respuesta = self.client.post('/en/accounts/register/', {'first_name': 'Ana', 'email': 'nueva@example.com', 'password1': 'debil', 'accepted_terms': 'on'})
        self.assertEqual(textos_en_espanol(respuesta.content.decode()), [])
        self.assertContains(respuesta, 'The password must have')

    def test_registro_con_correo_repetido(self):
        respuesta = self.client.post('/en/accounts/register/', {
            'first_name': 'Ana', 'email': 'ana-en@example.com', 'password1': 'Clave-Segura-123', 'accepted_terms': 'on',
        })
        self.assertContains(respuesta, 'already registered')
        self.assertEqual(textos_en_espanol(respuesta.content.decode()), [])

    def test_recuperar_contrasena_envia_el_correo_en_ingles(self):
        from django.core import mail
        self.client.post('/en/accounts/password_reset/', {'email': 'ana-en@example.com'})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Reset your GoToGym password')
        self.assertIn('To choose a new one, open this link:', mail.outbox[0].body)
        self.assertEqual(textos_en_espanol(mail.outbox[0].body), [])

    # --- cliente con sesion ------------------------------------------------------
    def test_cuenta_del_cliente(self):
        self.client.force_login(self.cliente)
        for ruta in ('/en/accounts/editar-perfil/', '/en/accounts/direcciones/nueva/', '/en/pedidos-tienda/mis-pedidos/'):
            with self.subTest(ruta=ruta):
                self._ver(ruta)

    def test_checkout_pedido_y_pago(self):
        self.client.force_login(self.cliente)
        self._con_carrito()
        self._ver('/en/pedidos-tienda/checkout/')
        # Formulario incompleto: los errores tambien salen en ingles.
        respuesta = self.client.post('/en/pedidos-tienda/checkout/', {'first_name': 'Ana'})
        self.assertEqual(textos_en_espanol(respuesta.content.decode()), [])
        pedido = create_order_from_cart(self.cliente, {str(self.variante.pk): 2}, DATOS)
        self._ver(f'/en/pedidos-tienda/pedido/{pedido.order_number}/')
        self._ver(f'/en/pagos/pedido/{pedido.order_number}/')

    def test_los_correos_del_pedido_salen_en_el_idioma_en_que_se_hizo(self):
        from django.core import mail
        from orders.models import Order
        from orders.services import apply_order_status_transition, confirm_payment
        pedido = create_order_from_cart(self.cliente, {str(self.variante.pk): 1}, DATOS)
        self.assertEqual(pedido.language, 'en')
        translation.activate('es')  # quien confirma el pago (webhook) no tiene idioma propio
        with self.captureOnCommitCallbacks(execute=True):
            confirm_payment(pedido, type('Pago', (), {'status': 'approved'})())
            apply_order_status_transition(Order.objects.get(pk=pedido.pk), 'shipped')
        asuntos = [correo.subject for correo in mail.outbox]
        self.assertEqual(asuntos, [f'We confirmed your order {pedido.order_number}', f'Your order {pedido.order_number} is on its way'])
        for correo in mail.outbox:
            self.assertEqual(textos_en_espanol(correo.body), [], correo.subject)
        self.assertIn('Subtotal:', mail.outbox[0].body)

    def test_mensajes_de_la_cuenta_en_ingles(self):
        self.client.force_login(self.cliente)
        respuesta = self.client.post('/en/accounts/editar-perfil/', {'first_name': 'Ana', 'age': 'abc'})
        mensajes = [str(m) for m in get_messages(respuesta.wsgi_request)]
        self.assertEqual(mensajes, ['Age must be a valid number.'])

    def test_pagina_404(self):
        respuesta = self.client.get('/en/no-existe/')
        self.assertEqual(respuesta.status_code, 404)

    # --- el selector -------------------------------------------------------------
    def test_el_espanol_sigue_igual(self):
        translation.activate('es')
        respuesta = self.client.get('/es/politica-cookies/')
        self.assertContains(respuesta, 'Política de cookies')
        self.assertNotContains(respuesta, 'Cookie policy')
