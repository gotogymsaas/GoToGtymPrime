"""Ficha del producto en el panel: edicion de los atributos visuales y su origen."""
from decimal import Decimal

from django.test import TestCase
from products import atributos
from products.models import Product, ProductCategory

from .forms import ProductAdminForm


class FichaDelPanelTests(TestCase):
    def setUp(self):
        self.categoria = ProductCategory.objects.create(name='Panel atributos')

    def _datos(self, **cambios):
        datos = {
            'name': 'Chaqueta gris', 'category': self.categoria.pk, 'line': '', 'brand': '',
            'description': '', 'base_price': '100000', 'discount': '0', 'stock': '0',
            'garment_type': 'chaqueta', 'sleeve': '', 'neckline': '', 'fit': '', 'pattern': '',
        }
        datos.update(cambios)
        return datos

    def test_cambiar_un_atributo_lo_marca_como_revisado(self):
        producto = Product.objects.create(name='Chaqueta gris', category=self.categoria, base_price=Decimal('1'))
        self.assertEqual(producto.visual_attributes_origin, atributos.ORIGEN_INFERIDO)

        formulario = ProductAdminForm(data=self._datos(fit='holgado'), instance=producto)
        self.assertTrue(formulario.is_valid(), formulario.errors)
        producto = formulario.save()

        self.assertEqual(producto.fit, 'holgado')
        self.assertEqual(producto.visual_attributes_origin, atributos.ORIGEN_MANUAL)

    def test_guardar_sin_tocar_conserva_el_origen_deducido(self):
        producto = Product.objects.create(name='Chaqueta gris', category=self.categoria, base_price=Decimal('1'))

        formulario = ProductAdminForm(data=self._datos(), instance=producto)
        self.assertTrue(formulario.is_valid(), formulario.errors)

        self.assertEqual(formulario.save().visual_attributes_origin, atributos.ORIGEN_INFERIDO)

    def test_guardar_una_propuesta_de_la_ia_la_confirma(self):
        producto = Product.objects.create(
            name='Chaqueta gris', category=self.categoria, base_price=Decimal('1'),
            visual_attributes_origin=atributos.ORIGEN_IA)

        formulario = ProductAdminForm(data=self._datos(), instance=producto)
        self.assertIn('Los propuso la IA', formulario.fields['garment_type'].help_text)
        self.assertTrue(formulario.is_valid(), formulario.errors)

        self.assertEqual(formulario.save().visual_attributes_origin, atributos.ORIGEN_MANUAL)
