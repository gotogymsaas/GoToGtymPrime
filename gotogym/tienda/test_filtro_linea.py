"""Filtro de linea (dama / caballero) del listado de la tienda."""
from django.test import TestCase
from django.urls import reverse
from vendedor.test_utilidades import aislar_catalogo, crear_producto


class FiltroDeLineaTests(TestCase):
    def setUp(self):
        aislar_catalogo()
        self.dama, _ = crear_producto('Top para dama', [('M', 'gris', 3)])
        self.caballero, _ = crear_producto('Chaqueta para caballero', [('L', 'negro', 3)])
        self.unisex, _ = crear_producto('Gorra unisex', [('UNICA', 'negro', 3)])
        self.sin_linea, _ = crear_producto('Botella deportiva', [('UNICA', 'azul', 3)])

    def _nombres(self, **parametros):
        respuesta = self.client.get(reverse('tienda:producto_list'), parametros)
        self.assertEqual(respuesta.status_code, 200)
        return {tarjeta['product'].name for tarjeta in respuesta.context['cards']}

    def test_sin_filtro_se_ve_todo_el_catalogo(self):
        self.assertEqual(
            self._nombres(),
            {'Top para dama', 'Chaqueta para caballero', 'Gorra unisex', 'Botella deportiva'},
        )

    def test_caballero_muestra_caballero_y_unisex(self):
        self.assertEqual(self._nombres(linea='caballero'), {'Chaqueta para caballero', 'Gorra unisex'})

    def test_dama_muestra_dama_y_unisex(self):
        self.assertEqual(self._nombres(linea='dama'), {'Top para dama', 'Gorra unisex'})

    def test_un_valor_desconocido_se_ignora(self):
        respuesta = self.client.get(reverse('tienda:producto_list'), {'linea': 'otra'})
        self.assertEqual(respuesta.context['selected_line'], '')
        self.assertEqual(len(respuesta.context['cards']), 4)

    def test_el_filtro_activo_se_muestra_y_se_puede_quitar(self):
        respuesta = self.client.get(reverse('tienda:producto_list'), {'linea': 'dama'})
        self.assertTrue(respuesta.context['filtros_activos'])
        self.assertContains(respuesta, 'name="linea" value="dama" checked')
        self.assertEqual(str(respuesta.context['selected_line_name']), 'Dama')
