"""Dias habiles de Colombia: los plazos de validacion y de pago dependen de
que los festivos se calculen bien."""
from datetime import date

from django.test import SimpleTestCase

from .dias_habiles import enesimo_dia_habil_del_mes, es_habil, festivos, sumar_dias_habiles


class FestivosTests(SimpleTestCase):
    def test_festivos_de_2026(self):
        esperados = {
            date(2026, 1, 1), date(2026, 1, 12), date(2026, 3, 23), date(2026, 4, 2), date(2026, 4, 3),
            date(2026, 5, 1), date(2026, 5, 18), date(2026, 6, 8), date(2026, 6, 15), date(2026, 6, 29),
            date(2026, 7, 20), date(2026, 8, 7), date(2026, 8, 17), date(2026, 10, 12), date(2026, 11, 2),
            date(2026, 11, 16), date(2026, 12, 8), date(2026, 12, 25),
        }
        self.assertEqual(festivos(2026), esperados)

    def test_festivos_de_2025(self):
        esperados = {
            date(2025, 1, 1), date(2025, 1, 6), date(2025, 3, 24), date(2025, 4, 17), date(2025, 4, 18),
            date(2025, 5, 1), date(2025, 6, 2), date(2025, 6, 23), date(2025, 6, 30), date(2025, 7, 20),
            date(2025, 8, 7), date(2025, 8, 18), date(2025, 10, 13), date(2025, 11, 3), date(2025, 11, 17),
            date(2025, 12, 8), date(2025, 12, 25),
        }
        self.assertEqual(festivos(2025), esperados)

    def test_fines_de_semana_y_festivos_no_son_habiles(self):
        self.assertFalse(es_habil(date(2026, 10, 10)))  # sabado
        self.assertFalse(es_habil(date(2026, 10, 11)))  # domingo
        self.assertFalse(es_habil(date(2026, 10, 12)))  # festivo (lunes)
        self.assertTrue(es_habil(date(2026, 10, 13)))


class SumarDiasHabilesTests(SimpleTestCase):
    def test_cinco_dias_habiles_desde_un_lunes_es_el_lunes_siguiente(self):
        self.assertEqual(sumar_dias_habiles(date(2026, 9, 7), 5), date(2026, 9, 14))

    def test_se_salta_fines_de_semana(self):
        self.assertEqual(sumar_dias_habiles(date(2026, 9, 11), 1), date(2026, 9, 14))  # viernes -> lunes

    def test_se_salta_festivos(self):
        # Entrega el jueves 8 de octubre de 2026: el lunes 12 es festivo.
        self.assertEqual(sumar_dias_habiles(date(2026, 10, 8), 5), date(2026, 10, 16))

    def test_el_dia_de_partida_no_cuenta_aunque_sea_fin_de_semana(self):
        self.assertEqual(sumar_dias_habiles(date(2026, 9, 12), 1), date(2026, 9, 14))

    def test_cero_dias_devuelve_la_misma_fecha(self):
        self.assertEqual(sumar_dias_habiles(date(2026, 9, 12), 0), date(2026, 9, 12))


class DiaHabilDelMesTests(SimpleTestCase):
    def test_decimo_dia_habil_de_noviembre_de_2026(self):
        # El 2 y el 16 son festivos: habiles 3-6, 9-13 (9 dias) y el 17 es el decimo.
        self.assertEqual(enesimo_dia_habil_del_mes(2026, 11, 10), date(2026, 11, 17))

    def test_primer_dia_habil_de_enero_de_2026(self):
        self.assertEqual(enesimo_dia_habil_del_mes(2026, 1, 1), date(2026, 1, 2))
