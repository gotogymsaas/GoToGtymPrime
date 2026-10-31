"""Firma HMAC de las solicitudes al Coach."""
from django.test import SimpleTestCase

from . import firma

SECRETO = 'secreto-de-prueba'
CUERPO = b'{"message":"hola"}'
AHORA = 1_790_000_000


class FirmaTests(SimpleTestCase):
    def _firmada(self, cuerpo=CUERPO):
        return firma.encabezados_firmados('clave-1', SECRETO, cuerpo, ahora=AHORA)

    def test_las_cabeceras_incluyen_clave_marca_y_firma(self):
        cabeceras = self._firmada()

        self.assertEqual(cabeceras[firma.ENCABEZADO_CLAVE], 'clave-1')
        self.assertEqual(cabeceras[firma.ENCABEZADO_MARCA], str(AHORA))
        self.assertEqual(len(cabeceras[firma.ENCABEZADO_FIRMA]), 64)

    def test_una_firma_valida_se_verifica(self):
        cabeceras = self._firmada()

        firma.verificar(
            SECRETO, cabeceras[firma.ENCABEZADO_MARCA], CUERPO,
            cabeceras[firma.ENCABEZADO_FIRMA], ahora=AHORA,
        )

    def test_la_firma_es_determinista(self):
        self.assertEqual(self._firmada(), self._firmada())

    def test_un_cuerpo_alterado_no_verifica(self):
        cabeceras = self._firmada()

        with self.assertRaises(firma.FirmaInvalida) as ctx:
            firma.verificar(
                SECRETO, cabeceras[firma.ENCABEZADO_MARCA], b'{"message":"otro"}',
                cabeceras[firma.ENCABEZADO_FIRMA], ahora=AHORA,
            )
        self.assertEqual(ctx.exception.motivo, 'no_coincide')

    def test_otro_secreto_no_verifica(self):
        cabeceras = self._firmada()

        with self.assertRaises(firma.FirmaInvalida) as ctx:
            firma.verificar(
                'otro-secreto', cabeceras[firma.ENCABEZADO_MARCA], CUERPO,
                cabeceras[firma.ENCABEZADO_FIRMA], ahora=AHORA,
            )
        self.assertEqual(ctx.exception.motivo, 'no_coincide')

    def test_la_marca_de_tiempo_forma_parte_de_lo_firmado(self):
        cabeceras = self._firmada()

        with self.assertRaises(firma.FirmaInvalida) as ctx:
            firma.verificar(
                SECRETO, str(AHORA + 1), CUERPO,
                cabeceras[firma.ENCABEZADO_FIRMA], ahora=AHORA,
            )
        self.assertEqual(ctx.exception.motivo, 'no_coincide')

    def test_una_solicitud_fuera_de_la_ventana_esta_expirada(self):
        cabeceras = self._firmada()

        for desfase in (firma.VENTANA_SEGUNDOS + 1, -(firma.VENTANA_SEGUNDOS + 1)):
            with self.subTest(desfase=desfase), self.assertRaises(firma.FirmaInvalida) as ctx:
                firma.verificar(
                    SECRETO, cabeceras[firma.ENCABEZADO_MARCA], CUERPO,
                    cabeceras[firma.ENCABEZADO_FIRMA], ahora=AHORA + desfase,
                )
            self.assertEqual(ctx.exception.motivo, 'expirada')

    def test_en_el_borde_de_la_ventana_todavia_vale(self):
        cabeceras = self._firmada()

        firma.verificar(
            SECRETO, cabeceras[firma.ENCABEZADO_MARCA], CUERPO,
            cabeceras[firma.ENCABEZADO_FIRMA], ahora=AHORA + firma.VENTANA_SEGUNDOS,
        )

    def test_marca_o_firma_mal_formadas(self):
        casos = [('no-es-numero', 'abc'), (str(AHORA), ''), (str(AHORA), None), (None, 'abc')]
        for marca, valor in casos:
            with self.subTest(marca=marca, firma=valor), self.assertRaises(firma.FirmaInvalida) as ctx:
                firma.verificar(SECRETO, marca, CUERPO, valor, ahora=AHORA)
            self.assertEqual(ctx.exception.motivo, 'malformada')

    def test_sin_secreto_no_se_firma(self):
        with self.assertRaises(firma.SecretoNoConfigurado):
            firma.encabezados_firmados('clave-1', '', CUERPO, ahora=AHORA)

    def test_sin_identificador_de_clave_no_se_firma(self):
        with self.assertRaises(firma.SecretoNoConfigurado):
            firma.encabezados_firmados('', SECRETO, CUERPO, ahora=AHORA)

    def test_el_error_no_expone_firma_ni_cuerpo(self):
        cabeceras = self._firmada()

        with self.assertRaises(firma.FirmaInvalida) as ctx:
            firma.verificar(
                SECRETO, cabeceras[firma.ENCABEZADO_MARCA], b'otro',
                cabeceras[firma.ENCABEZADO_FIRMA], ahora=AHORA,
            )
        self.assertEqual(str(ctx.exception), 'no_coincide')
