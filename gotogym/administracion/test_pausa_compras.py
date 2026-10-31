"""Pausa de compras: con el ajuste activo, carrito y checkout se bloquean sin tocar
el stock. El interruptor ya no esta en el panel (lo reemplazo el del Coach); estas
pruebas fijan las protecciones, que siguen vigentes si el ajuste se activa."""
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from inventory.models import Inventory
from orders.services import CheckoutError, create_order_from_cart
from products.models import Product, ProductCategory, ProductVariant

from administracion.models import PanelSettings
from administracion.test_admin_panel import PanelAdminBaseTestCase


class PausaDeComprasTests(PanelAdminBaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        categoria = ProductCategory.objects.create(name='Categoría pausa')
        producto = Product.objects.create(name='Producto pausa', category=categoria, base_price=Decimal('10000'))
        cls.variante = ProductVariant.objects.create(product=producto, sku='PAU-001', size='M', color='Negro')
        cls.inventario = Inventory.objects.create(variant=cls.variante, quantity_available=7)

    def _pausar(self, valor='1'):
        ajustes = PanelSettings.load()
        ajustes.purchases_paused = valor == '1'
        ajustes.purchases_paused_at = timezone.now() if valor == '1' else None
        ajustes.save()

    def test_por_defecto_las_compras_estan_activas(self):
        self.assertFalse(PanelSettings.compras_pausadas())

    def test_pausadas_no_se_puede_agregar_al_carrito(self):
        self._pausar('1')
        respuesta = self.client.post(
            reverse('carrito:add_to_cart', args=[self.variante.pk]), HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(self.client.session.get('cart', {}), {})

    def test_pausadas_no_se_puede_subir_la_cantidad_pero_si_quitar(self):
        self.client.post(reverse('carrito:add_to_cart', args=[self.variante.pk]))
        self._pausar('1')
        subir = self.client.post(
            reverse('carrito:update_cart', args=[self.variante.pk]), {'cantidad': 3},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(subir.status_code, 400)
        quitar = self.client.post(
            reverse('carrito:remove_from_cart', args=[self.variante.pk]), HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(quitar.status_code, 200)

    def test_pausadas_el_checkout_redirige_al_carrito(self):
        self.client.post(reverse('carrito:add_to_cart', args=[self.variante.pk]))
        self._pausar('1')
        respuesta = self.client.get(reverse('orders:checkout'))
        self.assertRedirects(respuesta, reverse('carrito:cart_detail'))

    def test_pausadas_no_se_crea_el_pedido_aunque_el_carrito_ya_estuviera_lleno(self):
        self._pausar('1')
        with self.assertRaises(CheckoutError):
            create_order_from_cart(self.cliente, {str(self.variante.pk): 1}, {})

    def test_reanudadas_se_puede_agregar_otra_vez(self):
        self._pausar('1')
        self._pausar('0')
        respuesta = self.client.post(
            reverse('carrito:add_to_cart', args=[self.variante.pk]), HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(respuesta.status_code, 200)

    def test_la_tienda_avisa_que_las_compras_estan_en_pausa(self):
        self._pausar('1')
        respuesta = self.client.get(reverse('tienda:producto_list'))
        self.assertContains(respuesta, 'class="gtg-pausa"')
