"""Contrato del componente de lente gravitacional Quantum.

El campo se renderiza desde un unico partial y una unica hoja
(partials/_quantum_lens.html + static/css/quantum_lens.css). Antes existia
duplicado con clases .gravity-* para el Home y .quantum-field para el
dominio comercial, asi que estas pruebas fijan las dos condiciones que
hacen que no vuelva a divergir: que las tres paginas comerciales usen la
misma pieza, y que la clase no se solape con las orbitas de la entrada
publica, que son otro componente con nombre parecido.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory, ProductVariant


class QuantumLensTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            email='lens@example.com', username='lens', password='secret123',
            first_name='Lena',
        )
        category = ProductCategory.objects.create(name='Lens category')
        brand = Brand.objects.create(name='Lens brand')
        cls.product = Product.objects.create(
            name='Lens Motion Tee', category=category, brand=brand,
            base_price=Decimal('90000.0000'), featured=True,
        )
        variant = ProductVariant.objects.create(
            product=cls.product, sku='LENS-M-BLK', size='M', color='negro',
        )
        Inventory.objects.create(variant=variant, quantity_available=4)

    def _paginas_comerciales(self):
        return [
            reverse('logged_home'),
            reverse('tienda:producto_list'),
            reverse('tienda:producto_detail', args=[self.product.pk]),
        ]

    def test_home_tienda_y_ficha_comparten_el_mismo_componente(self):
        self.client.force_login(self.user)

        for url in self._paginas_comerciales():
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertIn('class="quantum-lens"', html)
                self.assertIn('css/quantum_lens.css', html)
                self.assertIn('js/quantum_lens.js', html)
                # Una sola instancia: los id de los degradados del SVG son
                # unicos salvo que se pase el parametro `variant`.
                self.assertEqual(html.count('data-quantum-lens'), 1)

    def test_ninguna_pagina_conserva_la_copia_antigua_del_campo(self):
        self.client.force_login(self.user)

        for url in self._paginas_comerciales():
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertNotIn('gravity-field', html)
                self.assertNotIn('data-gravity-field', html)

    def test_el_flujo_de_pago_no_gasta_cuadros_de_animacion(self):
        self.client.force_login(self.user)

        html = self.client.get(reverse('carrito:cart_detail')).content.decode()

        self.assertNotIn('data-quantum-lens', html)
        self.assertNotIn('quantum_lens.css', html)

    def test_la_entrada_publica_conserva_sus_orbitas_y_no_carga_la_lente(self):
        # .quantum-field (orbitas, home_figma.css) y .quantum-lens son dos
        # componentes distintos. Si la entrada llegara a cargar la hoja de
        # la lente, sus orbitas heredarian position/transform y se romperia.
        html = self.client.get(reverse('home')).content.decode()

        self.assertIn('class="quantum-field"', html)
        self.assertNotIn('quantum_lens.css', html)
        self.assertNotIn('quantum-lens', html)

    def test_la_franja_de_interferencia_ya_no_se_muestra_en_el_home(self):
        # La franja decorativa (.quantum-fringe--story) se probo y se
        # retiro del Home: quedaba como una banda de color ajena al resto
        # de la pagina en vez de leerse como transicion editorial.
        self.client.force_login(self.user)
        html = self.client.get(reverse('logged_home')).content.decode()

        self.assertNotIn('quantum-fringe', html)

    def test_toda_instancia_del_campo_declara_su_opacidad_como_variable_css(self):
        # --ql-coherent es el punto de partida que usa la decoherencia al
        # hacer scroll (quantum_lens.css). Si una hoja nueva vuelve a fijar
        # `opacity` a secas sobre .quantum-lens sin la variable, esa
        # instancia del campo nunca decae: se queda opaca sobre el
        # contenido cuando el usuario ya bajo mas alla de su seccion.
        #
        # Esto vive en los .css enlazados, no en el HTML de la pagina (que
        # es lo unico que trae el cliente de pruebas de Django), asi que se
        # verifica leyendo los archivos fuente directamente.
        import re

        from django.conf import settings

        patron_opacidad_suelta = re.compile(r'\.quantum-lens\s*\{[^}]*\bopacity:\s*\.\d')
        for nombre in ('store_home.css', 'commerce_editorial.css'):
            ruta = settings.BASE_DIR / 'static' / 'css' / nombre
            css = ruta.read_text(encoding='utf-8')
            with self.subTest(archivo=nombre):
                self.assertIn('--ql-coherent:', css)
                self.assertNotRegex(css, patron_opacidad_suelta)
