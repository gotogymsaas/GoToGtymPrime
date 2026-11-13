"""Dos solicitudes de reembolso simultaneas deben llegar al proveedor una vez.

Necesita bloqueo de fila real (PostgreSQL en el CI); en SQLite se omite.
"""
import threading
import time
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from orders.services import create_order_from_cart
from orders.test_confirm_payment import DATOS, _crear_variante
from products.models import Brand, Product, ProductCategory

from .models import PaymentTransaction, Refund
from .services import RefundError, refund_order_payment


@skipUnlessDBFeature('has_select_for_update')
class ReembolsoSimultaneoTests(TransactionTestCase):
    def setUp(self):
        categoria = ProductCategory.objects.create(name='Categoria reembolso simultaneo')
        marca = Brand.objects.create(name='Marca reembolso simultaneo')
        producto = Product.objects.create(
            name='Producto reembolso simultaneo', category=categoria, brand=marca,
            base_price=Decimal('50000.0000'), stock=0,
        )
        variante = _crear_variante(producto, 'REEMB-SIM-S-NEG', 'S', 'negro', 5)
        Usuario = get_user_model()
        self.admin = Usuario.objects.create_user(
            email='admin-reemb-sim@example.com', username='admin-reemb-sim', password='x', is_staff=True,
        )
        self.pedido = create_order_from_cart(self.admin, {str(variante.pk): 1}, DATOS)
        PaymentTransaction.objects.create(
            order=self.pedido, provider='mock', payment_id='mock-pay-sim',
            external_reference=self.pedido.order_number,
            status=PaymentTransaction.Status.APPROVED, amount=self.pedido.total,
            idempotency_key='idem-reemb-sim',
        )

    def test_el_proveedor_recibe_una_sola_solicitud(self):
        llamadas = []

        def proveedor_lento(self_provider, transaccion, amount=None, idempotency_key=None):
            llamadas.append(idempotency_key)
            time.sleep(0.5)  # da tiempo a que la otra solicitud llegue al bloqueo
            return {'provider_refund_id': 'r-sim', 'status': 'approved'}

        resultados = [None, None]

        def solicitar(indice):
            try:
                resultados[indice] = refund_order_payment(self.pedido, self.admin)
            except RefundError as error:
                resultados[indice] = error
            finally:
                connections.close_all()

        with patch('payments.providers.mock.MockPaymentProvider.refund_payment', proveedor_lento):
            hilos = [threading.Thread(target=solicitar, args=(i,)) for i in range(2)]
            for hilo in hilos:
                hilo.start()
            for hilo in hilos:
                hilo.join(timeout=30)

        self.assertEqual(len(llamadas), 1, llamadas)
        self.assertEqual(sum(isinstance(r, Refund) for r in resultados), 1, resultados)
        self.assertEqual(sum(isinstance(r, RefundError) for r in resultados), 1, resultados)
        self.assertEqual(Refund.objects.filter(status=Refund.Status.APPROVED).count(), 1)
