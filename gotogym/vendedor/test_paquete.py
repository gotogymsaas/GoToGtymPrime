"""Paquete que la tienda envia al Coach: solo datos del servidor, sin datos
personales y dentro del presupuesto."""
import json
from decimal import Decimal
from unittest import mock

from analitica.services import hash_visitante
from carrito.services import CART_VERSION, SESSION_CART_KEY, SESSION_VERSION_KEY
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase, override_settings
from django.utils import translation
from inventory.services import get_available_quantity

from . import contrato, paquete
from .test_utilidades import aislar_catalogo, crear_producto

ANTES = 1_790_000_000


def _peticion(usuario=None, sesion=None, referer=None, host='testserver'):
    cabeceras = {'HTTP_HOST': host}
    if referer:
        cabeceras['HTTP_REFERER'] = referer
    request = RequestFactory().post('/es/vendedor/mensaje/', **cabeceras)
    request.user = usuario or AnonymousUser()
    request.session = {} if sesion is None else sesion
    return request


def _con_carrito(*pares):
    return {
        SESSION_CART_KEY: {str(variante.id): cantidad for variante, cantidad in pares},
        SESSION_VERSION_KEY: CART_VERSION,
    }


class PaqueteTests(TestCase):
    def setUp(self):
        aislar_catalogo()
        self.producto, self.variantes = crear_producto(
            'Leggins Quantum',
            [('S', 'gris', 2), ('M', 'gris', 5, {'price_override': Decimal('400000.0000')})],
            descripcion='Leggins color gris, tallas S y M. Hecho en microfibra.',
        )
        self.otro, self.variantes_otro = crear_producto('Camiseta', [('M', 'negro', 9)])

    def _armar(self, mensaje='Busco leggins para entrenar, talla M', **kwargs):
        peticion = kwargs.pop('peticion', None) or _peticion()
        with translation.override(kwargs.pop('idioma', 'es')):
            return paquete.armar_solicitud(
                peticion, mensaje, 'shop-abc', request_id='req-1', ahora=ANTES, **kwargs,
            )

    def test_el_paquete_cumple_el_contrato(self):
        solicitud = self._armar()

        contrato.validar_solicitud(solicitud)
        self.assertEqual(solicitud['request_id'], 'req-1')
        self.assertEqual(solicitud['conversation_id'], 'shop-abc')
        self.assertEqual(solicitud['timestamp'], ANTES)
        self.assertEqual(solicitud['locale'], 'es')

    def test_el_mensaje_viaja_sin_espacios_sobrantes(self):
        self.assertEqual(self._armar('  hola  ')['message'], 'hola')

    def test_el_idioma_sale_del_sitio(self):
        self.assertEqual(self._armar(idioma='en')['locale'], 'en')
        self.assertEqual(self._armar(idioma='pt')['locale'], 'es')

    def test_precios_y_existencias_de_los_candidatos_son_los_del_servidor(self):
        solicitud = self._armar()

        candidato = next(c for c in solicitud['evidence']['candidates'] if c['product_id'] == self.producto.id)
        reales = {v.id: v for v in self.variantes}
        for variante in candidato['variants']:
            real = reales[variante['id']]
            self.assertEqual(Decimal(variante['price']), real.effective_price)
            self.assertEqual(variante['available'], get_available_quantity(real))

    def test_el_carrito_sale_de_la_sesion_y_se_recalcula(self):
        _, m = self.variantes
        sesion = _con_carrito((m, 2))
        # Un cliente no puede decidir el precio: la sesion solo guarda cantidades.
        solicitud = self._armar(peticion=_peticion(sesion=sesion))

        self.assertEqual(solicitud['cart']['count'], 2)
        self.assertEqual(Decimal(solicitud['cart']['subtotal']), m.effective_price * 2)
        linea = solicitud['cart']['lines'][0]
        self.assertEqual(linea['variant_id'], m.id)
        self.assertEqual(linea['qty'], 2)
        self.assertEqual(linea['sku'], m.sku)
        self.assertEqual(Decimal(linea['unit_price']), m.effective_price)
        self.assertEqual(linea['available'], get_available_quantity(m))

    def test_los_productos_del_carrito_van_primero_entre_los_candidatos(self):
        sesion = _con_carrito((self.variantes_otro[0], 1))

        solicitud = self._armar('leggins', peticion=_peticion(sesion=sesion))

        ids = [c['product_id'] for c in solicitud['evidence']['candidates']]
        self.assertEqual(ids[0], self.otro.id)

    def test_un_carrito_de_version_anterior_se_ve_vacio_y_no_se_toca(self):
        sesion = {SESSION_CART_KEY: {str(self.variantes[0].id): 3}, SESSION_VERSION_KEY: CART_VERSION - 1}

        solicitud = self._armar(peticion=_peticion(sesion=sesion))

        self.assertEqual(solicitud['cart'], {'count': 0, 'subtotal': '0.00', 'lines': []})
        # La vista del carrito es quien avisa del reinicio; aqui no se limpia.
        self.assertEqual(sesion[SESSION_CART_KEY], {str(self.variantes[0].id): 3})
        self.assertEqual(sesion[SESSION_VERSION_KEY], CART_VERSION - 1)

    def test_el_carrito_ignora_variantes_inactivas(self):
        inactiva = self.variantes[0]
        inactiva.is_active = False
        inactiva.save()

        solicitud = self._armar(peticion=_peticion(sesion=_con_carrito((inactiva, 1))))

        self.assertEqual(solicitud['cart']['lines'], [])

    def test_las_compras_en_pausa_se_reflejan(self):
        with mock.patch.object(paquete, 'compras_pausadas', return_value=True):
            self.assertTrue(self._armar()['shop_flags']['purchases_paused'])
        with mock.patch.object(paquete, 'compras_pausadas', return_value=False):
            self.assertFalse(self._armar()['shop_flags']['purchases_paused'])

    def test_los_pagos_no_estan_en_vivo_por_defecto(self):
        self.assertFalse(self._armar()['shop_flags']['payments_live'])

    def test_los_pagos_en_vivo_exigen_proveedor_real_credenciales_y_panel(self):
        casos = [
            ('mercadopago', 'token', True, True),
            ('mock', 'token', True, False),
            ('mercadopago', '', True, False),
            ('mercadopago', 'token', False, False),
        ]
        for proveedor, token, habilitados, esperado in casos:
            with self.subTest(proveedor=proveedor, token=token, habilitados=habilitados), \
                    override_settings(PAYMENT_PROVIDER=proveedor, MERCADOPAGO_ACCESS_TOKEN=token), \
                    mock.patch.object(paquete, 'pagos_habilitados', return_value=habilitados):
                self.assertEqual(paquete.pagos_en_vivo(), esperado)

    def test_el_visitante_anonimo_tiene_un_seudonimo_estable(self):
        sesion = {}
        primero = self._armar(peticion=_peticion(sesion=sesion))['visitor']
        segundo = self._armar(peticion=_peticion(sesion=sesion))['visitor']

        self.assertEqual(primero, segundo)
        self.assertFalse(primero['authenticated'])
        self.assertTrue(primero['subject'].startswith('shop_v_'))

    def test_visitantes_distintos_tienen_seudonimos_distintos(self):
        uno = self._armar(peticion=_peticion(sesion={}))['visitor']['subject']
        otro = self._armar(peticion=_peticion(sesion={}))['visitor']['subject']

        self.assertNotEqual(uno, otro)

    def test_el_seudonimo_no_es_el_identificador_de_analitica(self):
        peticion = _peticion(sesion={})

        sujeto = self._armar(peticion=peticion)['visitor']['subject']

        self.assertNotIn(hash_visitante(peticion), sujeto)

    def test_el_paquete_de_un_usuario_no_lleva_datos_personales(self):
        usuario = get_user_model().objects.create_user(
            email='ana.marin@example.com', username='anita', password='secret123',
            first_name='Ana', last_name='Marín',
        )

        solicitud = self._armar(peticion=_peticion(usuario=usuario, sesion={}))

        cuerpo = contrato.serializar(solicitud).decode()
        for dato in ('ana.marin', 'example.com', 'anita', 'Marín', 'Ana '):
            self.assertNotIn(dato, cuerpo)
        self.assertTrue(solicitud['visitor']['authenticated'])
        self.assertTrue(solicitud['visitor']['subject'].startswith('shop_u_'))
        # No es el id del usuario ni se puede leer de vuelta: es un hash de 32 hex.
        self.assertRegex(solicitud['visitor']['subject'], r'^shop_u_[0-9a-f]{32}$')

    def test_el_mismo_usuario_siempre_tiene_el_mismo_seudonimo(self):
        usuario = get_user_model().objects.create_user(
            email='fijo@example.com', username='fijo', password='secret123',
        )

        uno = self._armar(peticion=_peticion(usuario=usuario, sesion={}))['visitor']['subject']
        otro = self._armar(peticion=_peticion(usuario=usuario, sesion={'otra': 'sesion'}))['visitor']['subject']

        self.assertEqual(uno, otro)

    def test_no_viajan_politicas_pendientes_con_su_texto(self):
        politicas = {p['key']: p for p in self._armar()['evidence']['policies']}

        self.assertEqual(politicas['devoluciones']['review_status'], 'pending_review')
        self.assertNotIn('30 días', politicas['devoluciones']['text'])

    def test_viajan_las_afirmaciones_prohibidas(self):
        afirmaciones = self._armar()['evidence']['claims_policy']

        self.assertIn('secado rápido', afirmaciones['prohibited'])
        self.assertTrue(afirmaciones['version'].startswith('sha256:'))

    def test_un_paquete_realista_cabe_con_holgura(self):
        solicitud = self._armar()

        self.assertLess(contrato.tamano_en_bytes(solicitud), contrato.MAX_BYTES_SOLICITUD // 2)

    def test_si_no_cabe_se_pierden_primero_los_ultimos_candidatos(self):
        foco, _ = crear_producto('En foco', [('M', 'negro', 1)], sort_order=0)
        tallas = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
        colores = [f'color-de-prueba-muy-largo-{numero:02d}' for numero in range(4)]
        for numero in range(contrato.MAX_CANDIDATOS + 2):
            crear_producto(
                f'Producto grande {numero} ' + 'x' * 100,
                [(talla, color, 3) for talla in tallas for color in colores],
                descripcion='d' * 400,
                sort_order=numero + 1,
                featured=True,
            )
        referer = f'http://testserver/es/tienda/producto/{foco.id}/'

        # Mensaje sin palabras del catalogo: el orden lo fijan solo el foco y el panel.
        solicitud = self._armar('hola', peticion=_peticion(referer=referer))

        candidatos = solicitud['evidence']['candidates']
        self.assertLessEqual(contrato.tamano_en_bytes(solicitud), contrato.MAX_BYTES_SOLICITUD)
        self.assertLess(len(candidatos), contrato.MAX_CANDIDATOS)
        self.assertEqual(candidatos[0]['product_id'], foco.id)

    def test_si_ni_vaciando_los_candidatos_cabe_no_se_envia(self):
        with mock.patch.object(contrato, 'MAX_BYTES_SOLICITUD', 500), \
                self.assertRaises(contrato.ContratoInvalido) as ctx:
            self._armar()
        self.assertEqual(str(ctx.exception), 'solicitud.tamano')

    def test_el_paquete_es_serializable_a_json(self):
        solicitud = self._armar()

        self.assertEqual(json.loads(contrato.serializar(solicitud)), solicitud)


class ContextoDePaginaTests(TestCase):
    def setUp(self):
        aislar_catalogo()
        self.producto, _ = crear_producto('Ficha', [('M', 'negro', 1)])

    def _pagina(self, referer, host='testserver'):
        with translation.override('es'):
            return paquete.contexto_de_pagina(_peticion(referer=referer, host=host))

    def test_sin_referer_no_hay_contexto(self):
        self.assertEqual(self._pagina(None)['url_name'], '')

    def test_la_ficha_de_un_producto_da_su_id(self):
        pagina = self._pagina(f'http://testserver/es/tienda/producto/{self.producto.id}/')

        self.assertEqual(pagina['url_name'], 'tienda:producto_detail')
        self.assertEqual(pagina['product_id'], self.producto.id)

    def test_el_listado_conserva_el_filtro_de_busqueda(self):
        pagina = self._pagina('http://testserver/es/tienda/?filtro=leggins')

        self.assertEqual(pagina['url_name'], 'tienda:producto_list')
        self.assertEqual(pagina['filtro'], 'leggins')
        self.assertIsNone(pagina['product_id'])

    def test_el_filtro_tiene_tope(self):
        pagina = self._pagina('http://testserver/es/tienda/?filtro=' + 'a' * 500)

        self.assertEqual(len(pagina['filtro']), paquete.MAX_LARGO_FILTRO)

    def test_un_referer_de_otro_sitio_se_ignora(self):
        pagina = self._pagina(f'http://otro.example/es/tienda/producto/{self.producto.id}/')

        self.assertEqual(pagina, {'url_name': '', 'product_id': None, 'variant_id': None, 'filtro': ''})

    def test_una_ruta_desconocida_se_ignora(self):
        self.assertEqual(self._pagina('http://testserver/es/no-existe/')['url_name'], '')

    def test_un_referer_basura_no_rompe(self):
        for basura in ('no es una url', 'http://', '://', 'javascript:alert(1)'):
            with self.subTest(basura=basura):
                self.assertEqual(self._pagina(basura)['product_id'], None)
