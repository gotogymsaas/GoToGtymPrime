"""Informes reales del panel admin (Fase 9): ventas por dia, productos mas
vendidos e ingresos, filtrables por rango de fechas."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from inventory.models import Inventory
from orders.services import confirm_payment, create_order_from_cart
from products.models import Brand, Product, ProductCategory, ProductVariant

DATOS = {
    'first_name': 'Ana', 'last_name': 'Marin', 'email': 'ana@example.com', 'phone': '3001234567',
    'country': 'Colombia', 'department': 'Bogotá D.C.', 'city': 'Bogotá',
    'address_line': 'Calle 100 # 15-20',
}


class _FakeTransaction:
    def __init__(self, status):
        self.status = status


def _crear_variante(producto, sku, size, color, stock):
    variante = ProductVariant.objects.create(product=producto, sku=sku, size=size, color=color)
    Inventory.objects.create(variant=variante, quantity_available=stock)
    return variante


class InformesAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = ProductCategory.objects.create(name='Categoria informes')
        marca = Brand.objects.create(name='Marca informes')
        cls.producto = Product.objects.create(
            name='Producto informes', category=categoria, brand=marca,
            base_price=Decimal('100000.0000'), stock=0,
        )
        cls.variante = _crear_variante(cls.producto, 'INF-REP-001-S-NEG', 'S', 'negro', 10)

        User = get_user_model()
        cls.cliente = User.objects.create_user(
            email='cliente-informes@example.com', username='cliente-informes@example.com', password='secret123',
        )
        cls.staff = User.objects.create_user(
            email='staff-informes@example.com', username='staff-informes@example.com', password='secret123',
            is_staff=True,
        )

    def test_anonimo_no_accede(self):
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_cliente_no_staff_no_accede(self):
        self.client.force_login(self.cliente)
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_un_pedido_pagado_aparece_en_el_resumen(self):
        pedido = create_order_from_cart(self.cliente, {str(self.variante.pk): 2}, DATOS)
        confirm_payment(pedido, _FakeTransaction('approved'))
        self.client.force_login(self.staff)

        response = self.client.get(reverse('admin_dashboard'))

        self.assertContains(response, self.producto.name)
        self.assertContains(response, '2')

    def test_un_pedido_sin_pagar_no_cuenta_en_los_ingresos(self):
        create_order_from_cart(self.cliente, {str(self.variante.pk): 1}, DATOS)
        self.client.force_login(self.staff)

        response = self.client.get(reverse('admin_dashboard'))

        self.assertContains(response, 'Sin ventas en este rango.')

    def test_filtrar_por_rango_de_fechas_excluye_pedidos_fuera_del_rango(self):
        pedido = create_order_from_cart(self.cliente, {str(self.variante.pk): 1}, DATOS)
        confirm_payment(pedido, _FakeTransaction('approved'))
        self.client.force_login(self.staff)

        response = self.client.get(reverse('admin_dashboard'), {'desde': '2000-01-01', 'hasta': '2000-01-02'})

        self.assertContains(response, 'Sin ventas en este rango.')
