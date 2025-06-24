<<<<<<< HEAD
from django.test import TestCase

# Create your tests here.
=======
from django.test import TestCase, RequestFactory
from unittest.mock import patch

from products.models import Category, Product
from .cart import SessionCart
from .views import CheckoutView


class CheckoutViewTests(TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.category = Category.objects.create(name="Test")
        self.product = Product.objects.create(
            name="Shirt", price=10, stock=5, category=self.category
        )

    @patch("integrations.mercadopago.mercadopago_client.MercadoPagoClient")
    def test_checkout_creates_preference(self, mock_mp):
        mock_mp.return_value.create_preference.return_value = {"init_point": "http://pay"}

        request = self.factory.post("/cart/checkout/")
        request.session = self.client.session

        cart = SessionCart(request)
        cart.add(self.product.id, 1)

        response = CheckoutView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        mock_mp.return_value.create_preference.assert_called_once()
>>>>>>> 0e6e1bad419e6ab057c6fb7929bf260f07e3bd01
