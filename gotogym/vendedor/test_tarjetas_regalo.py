"""Tarjetas de regalo en el turno del Coach: lo que la tienda declara en la
evidencia, la forma cerrada del bloque y el boton `open_gift_cards`."""
from django.apps import apps
from django.test import TestCase
from django.utils import translation

from . import contrato, paquete, respuesta
from .test_paquete import ANTES, _peticion
from .test_utilidades import aislar_catalogo, crear_producto


def _compras_pausadas(pausadas):
    PanelSettings = apps.get_model('administracion', 'PanelSettings')
    PanelSettings.objects.update_or_create(pk=1, defaults={'purchases_paused': pausadas})


class TarjetasEnLaEvidenciaTests(TestCase):
    def setUp(self):
        aislar_catalogo()
        crear_producto('Leggins Quantum', [('M', 'gris', 5)])

    def _solicitud(self):
        with translation.override('es'):
            return paquete.armar_solicitud(_peticion(), 'busco un regalo', 'shop-abc', request_id='req-1', ahora=ANTES)

    def test_viajan_el_rango_los_sugeridos_y_la_vigencia(self):
        tarjetas = self._solicitud()['evidence']['gift_cards']
        self.assertEqual(tarjetas, {
            'available': True, 'min_amount': '50000.00', 'max_amount': '1000000.00',
            'suggested_amounts': ['50000.00', '100000.00', '200000.00', '500000.00'], 'validity_months': 12,
        })

    def test_con_las_compras_en_pausa_no_estan_disponibles(self):
        _compras_pausadas(True)
        self.assertFalse(self._solicitud()['evidence']['gift_cards']['available'])

    def test_el_contrato_cierra_la_forma_del_bloque(self):
        solicitud = self._solicitud()
        contrato.validar_solicitud(solicitud)
        malos = (
            {'available': 'si'}, {'min_amount': 50000}, {'suggested_amounts': ['diez']},
            {'validity_months': 0}, {'codigo': 'ABCD'},
        )
        for cambio in malos:
            with self.subTest(cambio=cambio):
                rota = {**solicitud, 'evidence': {**solicitud['evidence'],
                                                  'gift_cards': {**solicitud['evidence']['gift_cards'], **cambio}}}
                with self.assertRaises(contrato.ContratoInvalido):
                    contrato.validar_solicitud(rota)


class BotonDeTarjetasTests(TestCase):
    def setUp(self):
        aislar_catalogo()
        crear_producto('Leggins Quantum', [('M', 'gris', 5)])
        with translation.override('es'):
            self.solicitud = paquete.armar_solicitud(_peticion(), 'es para mi hermana', 'shop-abc',
                                                     request_id='req-1', ahora=ANTES)

    def _sanear(self, acciones):
        validada = contrato.validar_respuesta({
            'reply': 'Si no sabes su talla, puedes regalarle una tarjeta.', 'ui_actions': acciones,
            'meta': {'status': 'ok', 'agents_used': [], 'evidence_refs': []},
        })
        with translation.override('es'):
            return respuesta.sanear(validada, self.solicitud)

    def test_la_direccion_y_el_texto_los_pone_la_tienda(self):
        segura = self._sanear([{'type': 'open_gift_cards', 'url': 'https://malicioso.example/', 'label': 'Gratis'}])
        self.assertEqual(segura.acciones, [{
            'type': 'open_gift_cards', 'url': '/es/tarjetas-regalo/', 'label': 'Ver tarjetas de regalo',
        }])

    def test_con_las_compras_en_pausa_se_descarta(self):
        _compras_pausadas(True)
        segura = self._sanear([{'type': 'open_gift_cards'}])
        self.assertEqual(segura.acciones, [])
        self.assertEqual(segura.descartadas, 1)
