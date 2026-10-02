"""Pagina "Acerca de": bloque de ciencia de materiales (grafeno)."""
import re

from django.test import TestCase
from django.urls import reverse


class AcercaDeCienciaTests(TestCase):
    def setUp(self):
        self.html = self.client.get(reverse('acerca_de')).content.decode()

    def test_es_publica_y_trae_el_bloque_de_grafeno(self):
        self.assertIn('id="grafeno"', self.html)
        self.assertIn('Grafeno: un átomo de espesor', self.html)

    def test_las_cifras_clave_estan_presentes(self):
        for dato in ('130', '4.840', '5.300', '401', '2,3 %', '38,4 s'):
            self.assertIn(dato, self.html, dato)

    def test_los_graficos_son_accesibles(self):
        self.assertEqual(self.html.count('role="img"'), 7)  # 2 graficos + 5 escalas de evidencia
        self.assertIn('Conductividad térmica: cobre frente a grafeno', self.html)
        self.assertIn('Del grafito al grafeno', self.html)

    def test_toda_cita_apunta_a_una_referencia_existente(self):
        citas = set(re.findall(r'href="#ref-(\d+)"', self.html))
        ids = set(re.findall(r'id="ref-(\d+)"', self.html))
        self.assertTrue(citas)
        self.assertLessEqual(citas, ids)

    def test_toda_referencia_se_cita_y_trae_enlace(self):
        citas = set(re.findall(r'href="#ref-(\d+)"', self.html))
        ids = set(re.findall(r'id="ref-(\d+)"', self.html))
        self.assertEqual(citas, ids)
        lista = self.html[self.html.index('class="science-references"'):]
        self.assertEqual(lista.count('Ver fuente'), len(ids))

    def test_aclara_que_no_describe_una_prenda_concreta(self):
        self.assertIn('no describe las propiedades de una prenda GoToGym en particular', self.html)

    def test_no_introduce_colores_hexadecimales_en_la_plantilla(self):
        from pathlib import Path
        fuente = (Path(__file__).parent / 'templates' / 'static_pages' / 'about.html').read_text(encoding='utf-8')
        self.assertEqual(re.findall(r'#[0-9A-Fa-f]{3,6}\b', fuente), [])


class TextoDelWelcomeTests(TestCase):
    def test_ya_no_menciona_un_producto_concreto(self):
        html = self.client.get(reverse('home')).content.decode()
        self.assertNotIn('X5', html)
        self.assertIn('Ropa deportiva con tecnología textil', html)
