"""Orden manual del catalogo: el que se arma arrastrando filas en Productos
es el mismo en que la tienda lista los productos."""
import importlib
from decimal import Decimal

from django.apps import apps as real_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory, ProductVariant
from tienda.catalog import ORDEN_DEL_PANEL


def _crear_producto(nombre, categoria, marca):
    producto = Product.objects.create(
        name=nombre, category=categoria, brand=marca, base_price=Decimal('50000'), stock=0,
    )
    variante = ProductVariant.objects.create(
        product=producto, sku=f'ORD-{producto.pk}-S-NEG', size='S', color='negro',
    )
    Inventory.objects.create(variant=variante, quantity_available=3)
    return producto


class OrdenDeProductosTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_user(
            email='admin-orden@example.com', username='admin-orden@example.com',
            password='secret123', is_staff=True,
        )
        categoria = ProductCategory.objects.create(name='Categoria orden')
        marca = Brand.objects.create(name='Marca orden')
        cls.a = _crear_producto('Orden A', categoria, marca)
        cls.b = _crear_producto('Orden B', categoria, marca)
        cls.c = _crear_producto('Orden C', categoria, marca)
        cls.d = _crear_producto('Orden D', categoria, marca)
        cls.propios = [cls.a, cls.b, cls.c, cls.d]

    def setUp(self):
        self.client.force_login(self.admin)

    def _reordenar(self, *productos):
        return self.client.post(
            reverse('admin_products_reorder'), {'product_id': [str(p.pk) for p in productos]},
        )

    def _orden_guardado(self):
        propios = {p.name for p in self.propios}
        return [p.name for p in Product.objects.order_by(*ORDEN_DEL_PANEL) if p.name in propios]

    def _orden_en_el_panel(self, **params):
        respuesta = self.client.get(reverse('admin_products'), params)
        propios = {p.name for p in self.propios}
        return [p.name for p in respuesta.context['products'] if p.name in propios]

    def _orden_en_la_tienda(self):
        respuesta = self.client.get(reverse('tienda:producto_list'))
        propios = {p.name for p in self.propios}
        return [card['product'].name for card in respuesta.context['cards'] if card['product'].name in propios]


class PosicionDeProductosNuevosTests(OrdenDeProductosTestCase):
    def test_un_producto_nuevo_queda_al_final(self):
        ultimo = Product.objects.order_by(*ORDEN_DEL_PANEL).last()
        self.assertEqual(ultimo.pk, self.d.pk)
        self.assertEqual(self._orden_guardado(), ['Orden A', 'Orden B', 'Orden C', 'Orden D'])

    def test_las_posiciones_no_se_repiten(self):
        posiciones = list(Product.objects.values_list('sort_order', flat=True))
        self.assertEqual(len(posiciones), len(set(posiciones)))
        self.assertNotIn(0, posiciones)

    def test_la_migracion_numera_los_productos_existentes_por_id(self):
        migracion = importlib.import_module('products.migrations.0016_product_sort_order')
        Product.objects.update(sort_order=0)

        migracion.numerar_productos(real_apps, None)

        ids = list(Product.objects.order_by('id').values_list('pk', flat=True))
        posiciones = list(Product.objects.order_by('id').values_list('sort_order', flat=True))
        self.assertEqual(posiciones, list(range(1, len(ids) + 1)))


class ReordenarProductosTests(OrdenDeProductosTestCase):
    def test_guarda_el_nuevo_orden(self):
        respuesta = self._reordenar(self.d, self.c, self.b, self.a)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self._orden_guardado(), ['Orden D', 'Orden C', 'Orden B', 'Orden A'])

    def test_el_panel_y_la_tienda_listan_en_ese_orden(self):
        self._reordenar(self.c, self.a, self.d, self.b)

        esperado = ['Orden C', 'Orden A', 'Orden D', 'Orden B']
        self.assertEqual(self._orden_en_el_panel(), esperado)
        self.assertEqual(self._orden_en_la_tienda(), esperado)

    def test_un_subconjunto_solo_cambia_entre_sus_propios_lugares(self):
        self._reordenar(self.c, self.a)

        self.assertEqual(self._orden_guardado(), ['Orden C', 'Orden B', 'Orden A', 'Orden D'])

    def test_los_demas_productos_conservan_su_lugar(self):
        antes = [p.pk for p in Product.objects.order_by(*ORDEN_DEL_PANEL)]

        self._reordenar(self.d, self.c, self.b, self.a)

        despues = [p.pk for p in Product.objects.order_by(*ORDEN_DEL_PANEL)]
        self.assertEqual(despues[:-4], antes[:-4])

    def test_renumera_de_1_a_n_sin_repetir(self):
        self._reordenar(self.b, self.a)

        posiciones = list(Product.objects.order_by(*ORDEN_DEL_PANEL).values_list('sort_order', flat=True))
        self.assertEqual(posiciones, list(range(1, len(posiciones) + 1)))

    def test_los_empates_heredados_no_dejan_el_orden_ambiguo(self):
        Product.objects.update(sort_order=0)

        self._reordenar(self.d, self.c, self.b, self.a)

        self.assertEqual(self._orden_guardado(), ['Orden D', 'Orden C', 'Orden B', 'Orden A'])
        posiciones = list(Product.objects.values_list('sort_order', flat=True))
        self.assertEqual(len(posiciones), len(set(posiciones)))

    def test_ignora_ids_invalidos_desconocidos_y_repetidos(self):
        respuesta = self.client.post(reverse('admin_products_reorder'), {
            'product_id': ['abc', '999999', str(self.c.pk), str(self.c.pk), str(self.a.pk)],
        })

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self._orden_guardado(), ['Orden C', 'Orden B', 'Orden A', 'Orden D'])

    def test_sin_ids_validos_responde_400_y_no_cambia_nada(self):
        antes = self._orden_guardado()

        respuesta = self.client.post(reverse('admin_products_reorder'), {'product_id': ['abc', '999999']})

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(self._orden_guardado(), antes)

    def test_solo_acepta_post(self):
        respuesta = self.client.get(reverse('admin_products_reorder'))
        self.assertEqual(respuesta.status_code, 405)

    def test_usuario_sin_permiso_no_puede_reordenar(self):
        cliente = get_user_model().objects.create_user(
            email='cliente-orden@example.com', username='cliente-orden@example.com', password='secret123',
        )
        self.client.force_login(cliente)
        antes = self._orden_guardado()

        respuesta = self._reordenar(self.d, self.c, self.b, self.a)

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self._orden_guardado(), antes)


class ListadoReordenableTests(OrdenDeProductosTestCase):
    def test_el_listado_trae_el_asa_de_arrastre_en_cada_fila(self):
        respuesta = self.client.get(reverse('admin_products'))

        self.assertContains(respuesta, 'class="drag-handle"', count=Product.objects.count())
        self.assertContains(respuesta, f'data-product-id="{self.a.pk}"')
        self.assertContains(respuesta, reverse('admin_products_reorder'))

    def test_el_listado_muestra_todos_los_productos_sin_paginar(self):
        respuesta = self.client.get(reverse('admin_products'))

        self.assertEqual(len(respuesta.context['products']), Product.objects.count())

    def test_con_una_busqueda_activa_no_se_puede_reordenar(self):
        respuesta = self.client.get(reverse('admin_products'), {'q': 'Orden'})

        self.assertEqual(len(respuesta.context['products']), 4)
        self.assertNotContains(respuesta, 'draggable="true"')
        self.assertContains(respuesta, 'Quita la búsqueda')

    def test_quien_solo_puede_ver_no_recibe_el_asa(self):
        # Un staff con un grupo que no incluye `change_product` ve el listado
        # pero no puede cambiarlo.
        from django.contrib.auth.models import Group, Permission

        lector = get_user_model().objects.create_user(
            email='lector-orden@example.com', username='lector-orden@example.com',
            password='secret123', is_staff=True,
        )
        grupo = Group.objects.create(name='Solo inventario orden')
        grupo.permissions.add(Permission.objects.get(
            content_type__app_label='inventory', codename='change_inventory',
        ))
        lector.groups.add(grupo)
        self.client.force_login(lector)

        respuesta = self.client.get(reverse('admin_products'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'draggable="true"')
