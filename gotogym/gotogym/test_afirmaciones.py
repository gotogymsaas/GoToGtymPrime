"""Afirmaciones sobre las prendas que el sitio no debe publicar.

Cada frase de la lista corresponde a una promesa sin respaldo medido. Las plantillas del sitio y el texto que
genera la ficha de producto no pueden contenerlas; el Journal queda fuera
porque explica esos conceptos con sus fuentes en lugar de prometerlos.
"""
import re
from pathlib import Path

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .afirmaciones import APROBADAS, PROHIBIDAS

RAIZ = Path(__file__).resolve().parent.parent


def _archivos_publicados():
    for plantilla in RAIZ.rglob('*.html'):
        partes = plantilla.relative_to(RAIZ).parts
        if 'templates' in partes and not {'.venv', 'node_modules', 'blog'} & set(partes):
            yield plantilla
    yield RAIZ / 'tienda' / 'catalog.py'


class AfirmacionesNoRespaldadasTests(SimpleTestCase):
    def test_ninguna_plantilla_ni_la_ficha_de_producto_las_contiene(self):
        hallazgos = []
        for archivo in _archivos_publicados():
            texto = archivo.read_text(encoding='utf-8').lower()
            texto = re.sub(r'&oacute;|&aacute;|&eacute;', lambda m: {'&oacute;': 'ó', '&aacute;': 'á', '&eacute;': 'é'}[m.group()], texto)
            for frase in PROHIBIDAS:
                if frase in texto:
                    hallazgos.append(f'{archivo.relative_to(RAIZ)}: "{frase}"')
        self.assertEqual(hallazgos, [])


class BancoDeAfirmacionesTests(TestCase):
    def test_cada_afirmacion_aprobada_tiene_fuente_y_vigencia(self):
        for afirmacion in APROBADAS:
            self.assertTrue(afirmacion.fuente, afirmacion.id)
            self.assertRegex(afirmacion.vigente_desde, r'^\d{4}-\d{2}-\d{2}$')

    def test_las_afirmaciones_aprobadas_se_publican_en_su_pagina(self):
        html = self.client.get(reverse('acerca_de')).content.decode()
        for afirmacion in APROBADAS:
            self.assertIn(afirmacion.texto, html, afirmacion.id)

    def test_ninguna_aprobada_es_una_frase_prohibida(self):
        for afirmacion in APROBADAS:
            for frase in PROHIBIDAS:
                self.assertNotIn(frase, afirmacion.texto.lower())
