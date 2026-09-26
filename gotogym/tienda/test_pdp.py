"""Ficha de producto: seleccion de variante, disponibilidad real y validacion."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory, ProductVariant

from tienda.catalog import LOW_STOCK_THRESHOLD, MAX_FEATURES, product_features


def _crear_producto(nombre, categoria, marca, precio='100000.0000'):
    return Product.objects.create(
        name=nombre, category=categoria, brand=marca,
        base_price=Decimal(precio), stock=0,
    )


def _crear_variante(producto, sku, size, color, stock):
    variante = ProductVariant.objects.create(product=producto, sku=sku, size=size, color=color)
    Inventory.objects.create(variant=variante, quantity_available=stock)
    return variante


class TiendaAutenticadaMixin:
    def setUp(self):
        super().setUp()
        User = get_user_model()
        correo = f'pdp-{self._testMethodName[:30]}@example.com'
        usuario = User.objects.create_user(email=correo, username=correo, password='secret123')
        self.client.force_login(usuario)


class FichaDeProductoTests(TiendaAutenticadaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = ProductCategory.objects.create(name='Categoria PDP')
        cls.marca = Brand.objects.create(name='Marca PDP')

        cls.multi = _crear_producto('Producto PDP multivariante', cls.categoria, cls.marca, '150000.0000')
        cls.v_s_negro = _crear_variante(cls.multi, 'PDP-001-S-NEG', 'S', 'negro', 4)
        cls.v_l_negro = _crear_variante(cls.multi, 'PDP-001-L-NEG', 'L', 'negro', 0)

        cls.unico = _crear_producto('Producto PDP variante unica', cls.categoria, cls.marca, '99000.0000')
        cls.v_unica = _crear_variante(cls.unico, 'PDP-002-U-UNI', 'UNICA', 'UNICO', 3)

        cls.agotado = _crear_producto('Producto PDP agotado', cls.categoria, cls.marca, '70000.0000')
        cls.v_agotada = _crear_variante(cls.agotado, 'PDP-003-S-NEG', 'S', 'negro', 0)

    def _url(self, producto):
        return reverse('tienda:producto_detail', args=[producto.pk])

    def test_la_ficha_expone_las_variantes_reales(self):
        response = self.client.get(self._url(self.multi))
        self.assertEqual(response.status_code, 200)
        skus = sorted(v['sku'] for v in response.context['variantes'])
        self.assertEqual(skus, ['PDP-001-L-NEG', 'PDP-001-S-NEG'])

    def test_marca_disponibilidad_por_variante(self):
        response = self.client.get(self._url(self.multi))
        por_sku = {v['sku']: v for v in response.context['variantes']}
        self.assertTrue(por_sku['PDP-001-S-NEG']['available'])
        self.assertFalse(por_sku['PDP-001-L-NEG']['available'])

    def test_producto_de_variante_unica_la_preselecciona(self):
        response = self.client.get(self._url(self.unico))
        self.assertIsNotNone(response.context['single_variant'])
        self.assertContains(response, f'value="{self.v_unica.id}"')

    def test_producto_de_variante_unica_muestra_talla_unica_marcada(self):
        response = self.client.get(self._url(self.unico))
        self.assertContains(response, 'data-size="UNICA"')
        self.assertContains(response, 'pdp-size--single')
        self.assertContains(response, 'aria-pressed="true"')
        self.assertNotContains(response, 'class="pdp-color')

    def test_producto_agotado_deshabilita_el_boton(self):
        response = self.client.get(self._url(self.agotado))
        self.assertFalse(response.context['in_stock'])
        self.assertContains(response, 'disabled')

    def test_no_muestra_datos_simulados(self):
        response = self.client.get(self._url(self.multi))
        contenido = response.content.decode()
        self.assertNotIn('reviews_count', contenido)
        self.assertNotIn('old_price', contenido)
        self.assertNotIn('long_description', contenido)
        self.assertNotIn('>star<', contenido)

    def test_muestra_placeholder_neutro_de_resenas(self):
        response = self.client.get(self._url(self.multi))
        self.assertContains(response, 'Sin rese')

    def test_no_queda_el_boton_comprar_ahora(self):
        response = self.client.get(self._url(self.multi))
        self.assertNotContains(response, 'Comprar ahora')


class SuperposicionYColapsoTests(TiendaAutenticadaMixin, TestCase):
    """Contrato de la firma visual de G1: la seleccion de variante como
    colapso de un estado en superposicion (ver commerce_editorial.css y
    el script de producto_detail.html).

    Estas pruebas fijan el marcado que el JS necesita para funcionar, no
    la animacion en si (eso requeriria un navegador real). Lo importante
    aqui es que el servidor nunca anime algo que no sea real: un precio
    fijo no debe representarse como incierto solo porque el producto tenga
    varias tallas.
    """

    @classmethod
    def setUpTestData(cls):
        cls.categoria = ProductCategory.objects.create(name='Categoria superposicion')
        cls.marca = Brand.objects.create(name='Marca superposicion')

        cls.precio_parejo = _crear_producto(
            'Producto precio parejo', cls.categoria, cls.marca, '100000.0000')
        _crear_variante(cls.precio_parejo, 'SUP-001-S-NEG', 'S', 'negro', 4)
        _crear_variante(cls.precio_parejo, 'SUP-001-M-NEG', 'M', 'negro', 4)

        cls.precio_variable = _crear_producto(
            'Producto precio variable', cls.categoria, cls.marca, '100000.0000')
        v_s = ProductVariant.objects.create(
            product=cls.precio_variable, sku='SUP-002-S-NEG', size='S', color='negro',
            price_override=Decimal('90000.0000'))
        Inventory.objects.create(variant=v_s, quantity_available=4)
        v_m = ProductVariant.objects.create(
            product=cls.precio_variable, sku='SUP-002-M-NEG', size='M', color='negro',
            price_override=Decimal('120000.0000'))
        Inventory.objects.create(variant=v_m, quantity_available=4)

        cls.unico = _crear_producto(
            'Producto superposicion variante unica', cls.categoria, cls.marca, '80000.0000')
        _crear_variante(cls.unico, 'SUP-003-U-UNI', 'UNICA', 'UNICO', 3)

    def _url(self, producto):
        return reverse('tienda:producto_detail', args=[producto.pk])

    def test_el_grupo_de_tallas_lleva_el_gancho_de_superposicion(self):
        # 'pdp-variant-group' a secas no basta: el JS de la pagina siempre
        # incluye ese nombre de clase en su propio codigo fuente, asi que
        # la cadena aparece aunque el fieldset no exista. Se busca el
        # patron exacto del atributo class que usan los partials.
        response = self.client.get(self._url(self.precio_parejo))
        self.assertContains(response, 'class="mb-4 pdp-variant-group"')

    def test_el_precio_parejo_no_se_marca_como_incierto(self):
        # Varias tallas no implican un precio incierto: si todas cuestan
        # igual, el precio no debe animarse como si estuviera en
        # superposicion.
        response = self.client.get(self._url(self.precio_parejo))
        self.assertFalse(response.context['has_price_range'])
        self.assertContains(response, 'data-has-range="false"')

    def test_el_precio_variable_si_se_marca_como_incierto(self):
        response = self.client.get(self._url(self.precio_variable))
        self.assertTrue(response.context['has_price_range'])
        self.assertContains(response, 'data-has-range="true"')

    def test_la_variante_unica_muestra_su_talla_resuelta(self):
        response = self.client.get(self._url(self.unico))
        self.assertContains(response, 'class="mb-4 pdp-variant-group"')
        self.assertContains(response, 'data-size="UNICA"')


class EspecificacionesDeLaFichaTests(TiendaAutenticadaMixin, TestCase):
    """Envio/cambios/garantia, guia de tallas y aviso de pocas unidades:
    la ficha solo mencionaba la marca, y todo lo demas que ayuda a decidir
    una compra (o a no arrepentirse de ella) estaba en el checkout o en el
    footer, nunca aqui."""

    @classmethod
    def setUpTestData(cls):
        cls.categoria = ProductCategory.objects.create(name='Categoria specs')
        cls.marca = Brand.objects.create(name='Marca specs')

        cls.pocas_unidades = _crear_producto('Producto pocas unidades', cls.categoria, cls.marca)
        _crear_variante(cls.pocas_unidades, 'SPEC-001-U-UNI', 'UNICA', 'UNICO', 2)

        cls.stock_normal = _crear_producto('Producto stock normal', cls.categoria, cls.marca)
        _crear_variante(cls.stock_normal, 'SPEC-002-U-UNI', 'UNICA', 'UNICO', 20)

        cls.con_tallas = _crear_producto('Producto con tallas', cls.categoria, cls.marca)
        _crear_variante(cls.con_tallas, 'SPEC-003-S-NEG', 'S', 'negro', 20)
        _crear_variante(cls.con_tallas, 'SPEC-003-M-NEG', 'M', 'negro', 2)

        cls.talla_unica = _crear_producto('Producto talla unica', cls.categoria, cls.marca)
        _crear_variante(cls.talla_unica, 'SPEC-004-U-UNI', 'UNICA', 'UNICO', 5)

    def _url(self, producto):
        return reverse('tienda:producto_detail', args=[producto.pk])

    def test_la_ficha_enlaza_envio_cambios_y_garantia(self):
        response = self.client.get(self._url(self.stock_normal))
        self.assertContains(response, reverse('politica_envios'))
        self.assertContains(response, reverse('politica_cambios'))
        self.assertContains(response, reverse('politica_garantia'))

    def test_variante_unica_con_pocas_unidades_avisa_en_el_servidor(self):
        # Con una sola variante no corre el JS de seleccion: el aviso tiene
        # que venir ya resuelto desde el servidor.
        response = self.client.get(self._url(self.pocas_unidades))
        self.assertContains(response, 'class="shop-pdp__low-stock"')

    def test_variante_unica_con_stock_normal_no_avisa(self):
        # 'Quedan pocas unidades' a secas no basta: ese texto tambien vive
        # en data-msg-low-stock, que se renderiza siempre (lo necesita el
        # JS del caso con varias tallas, sin importar el stock de este
        # producto). Se busca el <span> visible, no el mensaje en el
        # atributo.
        response = self.client.get(self._url(self.stock_normal))
        self.assertNotContains(response, 'class="shop-pdp__low-stock"')

    def test_el_umbral_viaja_al_js_para_el_caso_con_varias_tallas(self):
        # Con mas de una talla, el aviso lo decide el JS al elegir; el
        # servidor solo tiene que entregarle el umbral.
        response = self.client.get(self._url(self.con_tallas))
        self.assertContains(response, f'data-low-stock-threshold="{LOW_STOCK_THRESHOLD}"')

    def test_guia_de_tallas_aparece_solo_con_tallas_reconocidas(self):
        response = self.client.get(self._url(self.con_tallas))
        self.assertContains(response, 'Ver guía de tallas')
        self.assertContains(response, '<th scope="row">S</th>', html=True)
        self.assertContains(response, '<th scope="row">M</th>', html=True)

    def test_guia_de_tallas_no_aparece_para_talla_unica(self):
        # UNICA no tiene equivalencia en la guia: no hay nada que tabular.
        response = self.client.get(self._url(self.talla_unica))
        self.assertNotContains(response, 'Ver guía de tallas')

    def test_guia_de_tallas_se_marca_como_referencia_no_como_medida_exacta(self):
        response = self.client.get(self._url(self.con_tallas))
        self.assertContains(response, 'referencia general')


class CaracteristicasDeProductoTests(TestCase):
    """product_features segmenta la descripcion y la categoria en tarjetas
    con icono. Solo debe reflejar lo que el producto ya afirma: nada de
    propiedades termicas, medicas o de rendimiento inventadas."""

    @classmethod
    def setUpTestData(cls):
        # get_or_create, no create: 'Sport Premium' es un nombre real que
        # las migraciones de siembra del catalogo ya dejan en la base de
        # pruebas (ver products/migrations). Crearla de nuevo violaria la
        # restriccion de unicidad del nombre.
        cls.categoria_premium, _ = ProductCategory.objects.get_or_create(name='Sport Premium')
        cls.categoria_sin_mapa = ProductCategory.objects.create(name='Categoria sin mapear')
        cls.marca = Brand.objects.create(name='Marca features')

    def _producto(self, descripcion, categoria=None):
        return Product.objects.create(
            name='Producto features', category=categoria or self.categoria_premium,
            brand=self.marca, base_price=Decimal('100000.0000'),
            description=descripcion,
        )

    def test_la_categoria_siempre_aporta_una_tarjeta(self):
        producto = self._producto('')
        features = product_features(producto)
        self.assertEqual(len(features), 1)
        self.assertEqual(features[0]['label'], 'Línea premium')

    def test_categoria_sin_mapa_y_sin_descripcion_no_da_nada_inventado(self):
        producto = self._producto('', categoria=self.categoria_sin_mapa)
        self.assertEqual(product_features(producto), [])

    def test_detecta_material_y_uso_reales_de_la_descripcion(self):
        producto = self._producto('Camiseta en microfibra, uso deportivo.')
        etiquetas = [f['label'] for f in product_features(producto)]
        self.assertIn('Microfibra', etiquetas)
        self.assertIn('Uso deportivo', etiquetas)

    def test_nunca_repite_el_mismo_icono_en_un_producto(self):
        # 'casual' y la categoria 'Conjuntos' comparten icono (checkroom);
        # no deben aparecer las dos tarjetas a la vez. get_or_create: es
        # otro nombre real que ya siembra products/migrations.
        categoria_conjuntos, _ = ProductCategory.objects.get_or_create(name='Conjuntos')
        producto = self._producto('Prenda casual.', categoria=categoria_conjuntos)
        iconos = [f['icon'] for f in product_features(producto)]
        self.assertEqual(len(iconos), len(set(iconos)))

    def test_no_supera_el_maximo_de_tarjetas(self):
        producto = self._producto(
            'Microfibra, licra, grafeno, manga larga, ombliguera, deportivo, casual.'
        )
        self.assertLessEqual(len(product_features(producto)), MAX_FEATURES)

    def test_no_inventa_una_afirmacion_que_la_descripcion_no_hace(self):
        # Ningun producto de esta prueba menciona grafeno: la palabra no
        # puede aparecer en las tarjetas de ninguno de ellos.
        for descripcion in ['Camiseta en microfibra.', 'Talla unica, licra.', '']:
            with self.subTest(descripcion=descripcion):
                producto = self._producto(descripcion)
                etiquetas = ' '.join(f['label'] for f in product_features(producto))
                self.assertNotIn('grafeno', etiquetas.lower())


class OrdenDeLaFichaTests(TiendaAutenticadaMixin, TestCase):
    """Orden de la ficha, de arriba a abajo: lo que identifica el
    producto (descripcion), la decision de compra (guia de tallas,
    seleccion, boton), y solo despues los datos secundarios (marca,
    caracteristicas, envio/cambios/garantia al cierre). No es un orden
    arbitrario: cada cambio de posicion anterior salio de una correccion
    pedida sobre la version previa, asi que queda fijado con una prueba
    para que no se vuelva a revertir sin querer."""

    @classmethod
    def setUpTestData(cls):
        cls.categoria = ProductCategory.objects.create(name='Categoria orden')
        cls.marca = Brand.objects.create(name='Marca orden')
        cls.producto = Product.objects.create(
            name='Producto orden', category=cls.categoria, brand=cls.marca,
            base_price=Decimal('120000.0000'), description='Camiseta en microfibra.',
        )
        _crear_variante(cls.producto, 'ORD-001-S-NEG', 'S', 'negro', 5)
        _crear_variante(cls.producto, 'ORD-001-M-NEG', 'M', 'negro', 5)

    def test_el_orden_completo_es_descripcion_talla_marca_caracteristicas_politicas(self):
        response = self.client.get(reverse('tienda:producto_detail', args=[self.producto.pk]))
        html = response.content.decode()

        marcadores = [
            'shop-pdp__description',      # descripcion
            'pdp-variant-group',          # guia + seleccion de talla
            'Añadir al carrito',          # boton de compra
            'class="shop-pdp__specs"',    # marca
            'class="shop-pdp__features"', # caracteristicas
            'class="shop-pdp__policies"', # envio/cambios/garantia
        ]
        posiciones = [html.index(marcador) for marcador in marcadores]
        self.assertEqual(posiciones, sorted(posiciones))

    def test_envio_cambios_garantia_van_despues_del_boton_de_compra(self):
        response = self.client.get(reverse('tienda:producto_detail', args=[self.producto.pk]))
        html = response.content.decode()
        self.assertLess(html.index('Añadir al carrito'), html.index('class="shop-pdp__policies"'))


class EndpointDeVarianteTests(TiendaAutenticadaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = ProductCategory.objects.create(name='Categoria endpoint')
        cls.marca = Brand.objects.create(name='Marca endpoint')
        cls.producto = _crear_producto('Producto endpoint', cls.categoria, cls.marca, '110000.0000')
        cls.disponible = _crear_variante(cls.producto, 'END-001-S-NEG', 'S', 'negro', 2)
        cls.sin_stock = _crear_variante(cls.producto, 'END-001-M-NEG', 'M', 'negro', 0)

    def _url(self):
        return reverse('tienda:producto_variante', args=[self.producto.pk])

    def test_devuelve_datos_de_la_combinacion(self):
        response = self.client.get(self._url(), {'size': 'S', 'color': 'negro'})
        self.assertEqual(response.status_code, 200)
        datos = response.json()
        self.assertEqual(datos['sku'], 'END-001-S-NEG')
        self.assertEqual(datos['variant_id'], self.disponible.id)
        self.assertTrue(datos['available'])
        self.assertEqual(datos['stock'], 2)

    def test_available_false_cuando_no_hay_unidades(self):
        response = self.client.get(self._url(), {'size': 'M', 'color': 'negro'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['available'])

    def test_combinacion_inexistente_devuelve_404(self):
        response = self.client.get(self._url(), {'size': 'XXL', 'color': 'negro'})
        self.assertEqual(response.status_code, 404)

    def test_sin_parametros_devuelve_404(self):
        self.assertEqual(self.client.get(self._url()).status_code, 404)


class AgregarAlCarritoDesdeLaFichaTests(TiendaAutenticadaMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = ProductCategory.objects.create(name='Categoria add')
        cls.marca = Brand.objects.create(name='Marca add')

        cls.producto = _crear_producto('Producto add', cls.categoria, cls.marca)
        cls.v_ok = _crear_variante(cls.producto, 'ADD-001-S-NEG', 'S', 'negro', 3)
        cls.v_sin_stock = _crear_variante(cls.producto, 'ADD-001-L-NEG', 'L', 'negro', 0)

    def _url(self, variante):
        return reverse('carrito:add_to_cart', args=[variante.pk])

    def test_variante_con_stock_se_agrega(self):
        response = self.client.post(self._url(self.v_ok))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session['cart'], {str(self.v_ok.pk): 1})

    def test_variante_sin_stock_se_rechaza(self):
        response = self.client.post(self._url(self.v_sin_stock))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get('cart', {}), {})

    def test_variante_inexistente_devuelve_404(self):
        response = self.client.post(reverse('carrito:add_to_cart', args=[999999]))
        self.assertEqual(response.status_code, 404)

    def test_no_se_puede_superar_el_stock_disponible(self):
        for _ in range(3):
            self.client.post(self._url(self.v_ok))
        self.assertEqual(self.client.session['cart'], {str(self.v_ok.pk): 3})

        # La cuarta unidad excede el inventario y no debe modificar el carrito.
        self.client.post(self._url(self.v_ok))
        self.assertEqual(self.client.session['cart'], {str(self.v_ok.pk): 3})

    def test_peticion_ajax_sin_stock_devuelve_400(self):
        response = self.client.post(
            self._url(self.v_sin_stock), HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
