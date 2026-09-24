"""Checkout: validacion, creacion del pedido y congelado de los datos vendidos."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from carrito.services import CART_VERSION
from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory, ProductVariant

from shipping.models import ShippingQuote
from shipping.services import FREE_SHIPPING_THRESHOLD
from tienda.templatetags.tienda_filters import cop

from .forms import CheckoutForm
from .models import Address, Order, OrderItem, OrderStatus, PaymentStatus
from .services import (
    EmptyCartError,
    OutOfStockError,
    create_order_from_cart,
    generate_order_number,
)

DATOS_VALIDOS = {
    'first_name': 'Ana',
    'last_name': 'Marin',
    'email': 'ana@example.com',
    'phone': '3001234567',
    'country': 'Colombia',
    'department': 'Bogotá D.C.',
    'city': 'Bogotá',
    'postal_code': '110111',
    'address_line': 'Calle 100 # 15-20',
    'address_complement': 'Apto 501',
    'notes': 'Dejar en porteria',
}


def _crear_variante(producto, sku, size, color, stock):
    variante = ProductVariant.objects.create(product=producto, sku=sku, size=size, color=color)
    Inventory.objects.create(variant=variante, quantity_available=stock)
    return variante


class CheckoutBaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = ProductCategory.objects.create(name='Categoria checkout')
        cls.marca = Brand.objects.create(name='Marca checkout')
        cls.producto = Product.objects.create(
            name='Producto checkout', category=cls.categoria, brand=cls.marca,
            base_price=Decimal('120000.0000'), stock=0,
        )
        cls.variante = _crear_variante(cls.producto, 'CHK-001-S-NEG', 'S', 'negro', 5)

        cls.producto_b = Product.objects.create(
            name='Producto checkout B', category=cls.categoria, brand=cls.marca,
            base_price=Decimal('30000.0000'), stock=0,
        )
        cls.variante_b = _crear_variante(cls.producto_b, 'CHK-002-M-AZU', 'M', 'azul', 4)

    def setUp(self):
        super().setUp()
        User = get_user_model()
        correo = f'checkout-{self._testMethodName[:30]}@example.com'
        self.usuario = User.objects.create_user(email=correo, username=correo, password='secret123')
        self.client.force_login(self.usuario)

    def _poner_en_carrito(self, mapa):
        session = self.client.session
        session['cart'] = mapa
        session['cart_version'] = CART_VERSION
        session.save()


class NumeroDePedidoTests(TestCase):
    def test_formato_legible(self):
        numero = generate_order_number()
        self.assertRegex(numero, r'^GTG-\d{6}-\d{4}$')

    def test_es_secuencial_dentro_del_mes(self):
        primero = generate_order_number()
        Order.objects.create(order_number=primero, email='a@example.com', phone='300')
        segundo = generate_order_number()
        self.assertNotEqual(primero, segundo)
        self.assertEqual(int(segundo[-4:]), int(primero[-4:]) + 1)


class FormularioDeCheckoutTests(TestCase):
    def test_datos_validos_pasan(self):
        self.assertTrue(CheckoutForm(DATOS_VALIDOS).is_valid())

    def test_campos_obligatorios_faltantes(self):
        form = CheckoutForm({})
        self.assertFalse(form.is_valid())
        for campo in ['first_name', 'last_name', 'email', 'phone', 'country',
                      'department', 'city', 'address_line']:
            self.assertIn(campo, form.errors)

    def test_campos_opcionales_no_son_obligatorios(self):
        form = CheckoutForm(DATOS_VALIDOS)
        form.is_valid()
        for campo in ['postal_code', 'address_complement', 'notes']:
            self.assertNotIn(campo, form.errors)

    def test_email_invalido_se_rechaza(self):
        form = CheckoutForm({**DATOS_VALIDOS, 'email': 'no-es-un-correo'})
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_telefono_invalido_se_rechaza(self):
        form = CheckoutForm({**DATOS_VALIDOS, 'phone': 'abc'})
        self.assertFalse(form.is_valid())
        self.assertIn('phone', form.errors)

    def test_direccion_demasiado_corta_se_rechaza(self):
        form = CheckoutForm({**DATOS_VALIDOS, 'address_line': 'Cll'})
        self.assertFalse(form.is_valid())
        self.assertIn('address_line', form.errors)


class CreacionDePedidoTests(CheckoutBaseTestCase):
    def test_crea_un_pedido_con_sus_lineas_y_direccion(self):
        cart = {str(self.variante.pk): 2, str(self.variante_b.pk): 1}
        pedido = create_order_from_cart(self.usuario, cart, DATOS_VALIDOS)

        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(pedido.items.count(), 2)
        self.assertTrue(Address.objects.filter(order=pedido).exists())
        self.assertEqual(pedido.user, self.usuario)

    def test_el_pedido_nace_pendiente_de_pago(self):
        pedido = create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS_VALIDOS)
        self.assertEqual(pedido.order_status, OrderStatus.PENDING_PAYMENT)
        self.assertEqual(pedido.payment_status, PaymentStatus.PENDING)

    def test_el_total_es_la_suma_de_las_lineas_mas_el_envio(self):
        cart = {str(self.variante.pk): 2, str(self.variante_b.pk): 3}
        pedido = create_order_from_cart(self.usuario, cart, DATOS_VALIDOS)

        suma_lineas = sum(item.line_total for item in pedido.items.all())
        self.assertEqual(pedido.subtotal, suma_lineas)
        self.assertEqual(
            pedido.total, pedido.subtotal + pedido.shipping_cost - pedido.discount_total
        )

    def test_los_precios_salen_de_la_base_no_del_carrito(self):
        cart = {str(self.variante.pk): 1}
        pedido = create_order_from_cart(self.usuario, cart, DATOS_VALIDOS)
        # DATOS_VALIDOS usa Bogota (ciudad principal): subtotal 120000 + envio 12000.
        self.assertEqual(pedido.total, Decimal('132000.00'))

    def test_carrito_vacio_no_crea_pedido(self):
        with self.assertRaises(EmptyCartError):
            create_order_from_cart(self.usuario, {}, DATOS_VALIDOS)
        self.assertEqual(Order.objects.count(), 0)

    def test_stock_insuficiente_no_crea_pedido_a_medias(self):
        cart = {str(self.variante.pk): 1, str(self.variante_b.pk): 99}

        with self.assertRaises(OutOfStockError):
            create_order_from_cart(self.usuario, cart, DATOS_VALIDOS)

        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)
        self.assertEqual(Address.objects.count(), 0)

    def test_el_pedido_no_descuenta_inventario(self):
        # El stock solo baja cuando el pago se aprueba, no al crear el pedido.
        create_order_from_cart(self.usuario, {str(self.variante.pk): 2}, DATOS_VALIDOS)
        self.assertEqual(Inventory.objects.get(variant=self.variante).quantity_available, 5)


class SnapshotDelPedidoTests(CheckoutBaseTestCase):
    def test_la_linea_congela_los_datos_del_producto(self):
        pedido = create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS_VALIDOS)
        linea = pedido.items.get()

        self.assertEqual(linea.product_name_snapshot, 'Producto checkout')
        self.assertEqual(linea.sku_snapshot, 'CHK-001-S-NEG')
        self.assertEqual(linea.size_snapshot, 'S')
        self.assertEqual(linea.color_snapshot, 'negro')
        self.assertEqual(linea.unit_price_snapshot, Decimal('120000.00'))

    def test_cambiar_el_precio_despues_no_altera_el_pedido(self):
        pedido = create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS_VALIDOS)

        self.variante.price_override = Decimal('999000.0000')
        self.variante.save(update_fields=['price_override'])
        self.producto.name = 'Nombre cambiado'
        self.producto.save(update_fields=['name'])

        pedido.refresh_from_db()
        linea = pedido.items.get()
        self.assertEqual(linea.unit_price_snapshot, Decimal('120000.00'))
        self.assertEqual(linea.product_name_snapshot, 'Producto checkout')
        self.assertEqual(pedido.total, Decimal('132000.00'))

    def test_borrar_la_variante_no_borra_la_linea(self):
        pedido = create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS_VALIDOS)
        self.variante.delete()

        linea = pedido.items.get()
        self.assertIsNone(linea.variant)
        self.assertEqual(linea.sku_snapshot, 'CHK-001-S-NEG')


class VistaDeCheckoutTests(CheckoutBaseTestCase):
    def _url(self):
        return reverse('orders:checkout')

    def test_get_muestra_el_formulario_con_el_resumen(self):
        self._poner_en_carrito({str(self.variante.pk): 1})
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'CHK-001-S-NEG')

    def test_carrito_vacio_redirige_al_carrito(self):
        response = self.client.get(self._url())
        self.assertRedirects(response, reverse('carrito:cart_detail'))

    def test_post_valido_crea_el_pedido_y_vacia_el_carrito(self):
        self._poner_en_carrito({str(self.variante.pk): 2})
        response = self.client.post(self._url(), DATOS_VALIDOS)

        pedido = Order.objects.get()
        self.assertRedirects(
            response, reverse('payments:pending', args=[pedido.order_number])
        )
        self.assertEqual(self.client.session['cart'], {})

    def test_post_invalido_no_crea_pedido_ni_vacia_el_carrito(self):
        self._poner_en_carrito({str(self.variante.pk): 1})
        response = self.client.post(self._url(), {**DATOS_VALIDOS, 'email': 'malo'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(self.client.session['cart'], {str(self.variante.pk): 1})
        self.assertIn('email', response.context['form'].errors)

    def test_stock_insuficiente_mantiene_el_carrito(self):
        self._poner_en_carrito({str(self.variante.pk): 99})
        response = self.client.post(self._url(), DATOS_VALIDOS)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(self.client.session['cart'], {str(self.variante.pk): 99})

    def test_checkout_anonimo_redirige_a_login(self):
        self.client.logout()
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=', response.url)


class CotizacionEnVivoTests(CheckoutBaseTestCase):
    """El resumen del checkout mostraba "Sin costo por ahora" sin importar
    la ciudad, y su Total ni siquiera sumaba el envio (era subtotal a
    secas). Este endpoint calcula en vivo, con el mismo motor y el mismo
    subtotal que create_order_from_cart usa al confirmar, para que lo que
    el comprador ve aqui sea lo que termina pagando."""

    def _url(self, city=None):
        url = reverse('orders:cotizar_envio')
        return f'{url}?city={city}' if city else url

    def test_requiere_sesion_iniciada(self):
        self.client.logout()
        response = self.client.get(self._url('Bogotá'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=', response.url)

    def test_sin_ciudad_devuelve_400(self):
        self._poner_en_carrito({str(self.variante.pk): 1})
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 400)

    def test_carrito_vacio_devuelve_400(self):
        response = self.client.get(self._url('Bogotá'))
        self.assertEqual(response.status_code, 400)

    def test_coincide_con_lo_que_cobra_el_pedido_real(self):
        # La invariante central: cotizar antes de confirmar y confirmar
        # tienen que dar el mismo numero para la misma ciudad y el mismo
        # carrito, o el resumen estaria prometiendo algo que no cumple.
        self._poner_en_carrito({str(self.variante.pk): 1})

        respuesta = self.client.get(self._url('Bogotá'))
        self.assertEqual(respuesta.status_code, 200)
        cotizado = respuesta.json()['cost']

        pedido = create_order_from_cart(
            self.usuario, {str(self.variante.pk): 1}, DATOS_VALIDOS,
        )
        self.assertEqual(Decimal(str(cotizado)), pedido.shipping_cost)

    def test_ciudad_principal_cotiza_menos_que_resto_del_pais(self):
        self._poner_en_carrito({str(self.variante.pk): 1})

        cerca = self.client.get(self._url('Bogotá')).json()['cost']
        lejos = self.client.get(self._url('Leticia')).json()['cost']

        self.assertLess(cerca, lejos)

    def test_envio_gratis_por_encima_del_umbral(self):
        producto_caro = Product.objects.create(
            name='Producto caro cotizacion', category=self.categoria, brand=self.marca,
            base_price=FREE_SHIPPING_THRESHOLD, stock=0,
        )
        variante_cara = _crear_variante(producto_caro, 'COT-CARO-U-UNI', 'UNICA', 'UNICO', 1)
        self._poner_en_carrito({str(variante_cara.pk): 1})

        datos = self.client.get(self._url('Bogotá')).json()
        self.assertTrue(datos['is_free'])
        self.assertEqual(datos['cost'], 0)

    def test_ignora_cualquier_subtotal_que_mande_el_cliente(self):
        # El endpoint no acepta un parametro de subtotal: siempre usa el
        # carrito real en sesion, para que nadie pueda pedir la tarifa de
        # envio gratis mandando un monto inventado.
        self._poner_en_carrito({str(self.variante.pk): 1})

        url = reverse('orders:cotizar_envio')
        respuesta = self.client.get(f'{url}?city=Bogotá&subtotal=999999999')

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()['subtotal'], float(self.variante.effective_price))


class DetalleDePedidoTests(CheckoutBaseTestCase):
    def test_el_dueno_ve_su_pedido(self):
        pedido = create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS_VALIDOS)
        response = self.client.get(reverse('orders:order_detail', args=[pedido.order_number]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, pedido.order_number)

    def test_no_se_puede_ver_el_pedido_de_otro_usuario(self):
        pedido = create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS_VALIDOS)

        User = get_user_model()
        intruso = User.objects.create_user(
            email='intruso@example.com', username='intruso@example.com', password='secret123',
        )
        self.client.force_login(intruso)

        response = self.client.get(reverse('orders:order_detail', args=[pedido.order_number]))
        self.assertEqual(response.status_code, 404)


class EnvioIntegradoAlTotalTests(CheckoutBaseTestCase):
    """El envio deja de ser un numero fijo desconectado: se cotiza segun la
    ciudad de entrega y pasa a formar parte del mismo total que ve el
    carrito, la Order y el pago."""

    def test_se_crea_una_cotizacion_de_envio_junto_con_el_pedido(self):
        pedido = create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS_VALIDOS)
        self.assertTrue(ShippingQuote.objects.filter(order=pedido).exists())

    def test_el_costo_de_envio_de_la_orden_es_el_de_la_cotizacion(self):
        pedido = create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, DATOS_VALIDOS)
        cotizacion = ShippingQuote.objects.get(order=pedido)
        self.assertEqual(pedido.shipping_cost, cotizacion.cost)

    def test_ciudad_principal_cobra_menos_que_resto_del_pais(self):
        datos_lejos = {**DATOS_VALIDOS, 'city': 'Leticia'}
        cart = {str(self.variante.pk): 1}

        pedido_cerca = create_order_from_cart(self.usuario, cart, DATOS_VALIDOS)
        # Cada pedido consume la unica variante disponible; se repone stock
        # manualmente entre pedidos para poder comparar en el mismo test.
        Inventory.objects.filter(variant=self.variante).update(quantity_available=5)
        pedido_lejos = create_order_from_cart(self.usuario, cart, datos_lejos)

        self.assertLess(pedido_cerca.shipping_cost, pedido_lejos.shipping_cost)

    def test_envio_gratis_por_encima_del_umbral_se_refleja_en_la_orden(self):
        producto_caro = Product.objects.create(
            name='Producto caro checkout', category=self.categoria, brand=self.marca,
            base_price=FREE_SHIPPING_THRESHOLD, stock=0,
        )
        variante_cara = _crear_variante(producto_caro, 'CHK-CARO-U-UNI', 'UNICA', 'UNICO', 1)

        pedido = create_order_from_cart(self.usuario, {str(variante_cara.pk): 1}, DATOS_VALIDOS)
        self.assertEqual(pedido.shipping_cost, Decimal('0.00'))

    def test_invariante_total_igual_subtotal_mas_envio_menos_descuento(self):
        for datos in [DATOS_VALIDOS, {**DATOS_VALIDOS, 'city': 'Leticia'}]:
            with self.subTest(city=datos['city']):
                Inventory.objects.filter(variant=self.variante).update(quantity_available=5)
                pedido = create_order_from_cart(self.usuario, {str(self.variante.pk): 1}, datos)
                self.assertEqual(
                    pedido.total,
                    pedido.subtotal + pedido.shipping_cost - pedido.discount_total,
                )

    def test_checkout_muestra_el_envio_ya_incluido_en_el_total(self):
        session = self.client.session
        session['cart'] = {str(self.variante.pk): 1}
        session['cart_version'] = CART_VERSION
        session.save()

        response = self.client.post(reverse('orders:checkout'), DATOS_VALIDOS, follow=True)
        pedido = Order.objects.get()

        self.assertContains(response, f"${cop(pedido.shipping_cost)}")
        self.assertContains(response, f"${cop(pedido.total)}")


class TotalUnicoDePuntaAPuntaTests(CheckoutBaseTestCase):
    """Test critico: total carrito = total checkout = total Order = total
    Payment, verificado de punta a punta en un unico flujo."""

    def test_el_mismo_total_se_ve_en_carrito_checkout_order_y_pago(self):
        from carrito.services import build_cart_context
        from payments.models import PaymentTransaction
        from payments.providers.mock import MockPaymentProvider

        cart = {str(self.variante.pk): 2}

        # 1. Carrito: subtotal sin envio (todavia no hay direccion).
        contexto_carrito = build_cart_context(cart)
        self.assertEqual(contexto_carrito['subtotal'], Decimal('240000.00'))

        # 2. Checkout -> Order: el subtotal debe coincidir con el del carrito,
        #    y el total ya incluye el envio real de la ciudad elegida.
        pedido = create_order_from_cart(self.usuario, cart, DATOS_VALIDOS)
        self.assertEqual(pedido.subtotal, contexto_carrito['subtotal'])
        self.assertEqual(pedido.total, pedido.subtotal + pedido.shipping_cost)

        # 3. Payment: el monto a cobrar es exactamente el total de la orden.
        transaccion = MockPaymentProvider().create_payment_intent(pedido)
        self.assertEqual(transaccion.amount, pedido.total)
        self.assertEqual(PaymentTransaction.objects.get(order=pedido).amount, pedido.total)

        # 4. Lo que efectivamente se muestra en la pantalla de pago es ese
        #    mismo numero, no uno recalculado aparte.
        response = self.client.get(reverse('payments:pending', args=[pedido.order_number]))
        self.assertContains(response, f"${cop(pedido.total)}")
