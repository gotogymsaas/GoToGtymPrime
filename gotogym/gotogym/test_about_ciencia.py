"""Pagina "Acerca de": bloque de ciencia de materiales (grafeno)."""
import re

from django.test import TestCase
from django.utils import translation
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

    def test_no_introduce_colores_hexadecimales_en_la_plantilla(self):
        from pathlib import Path
        fuente = (Path(__file__).parent / 'templates' / 'static_pages' / 'about.html').read_text(encoding='utf-8')
        self.assertEqual(re.findall(r'#[0-9A-Fa-f]{3,6}\b', fuente), [])


class AcercaDeMarcaTests(TestCase):
    def setUp(self):
        self.html = self.client.get(reverse('acerca_de')).content.decode()

    def test_rotula_proposito_mision_y_vision_como_el_manual_de_marca(self):
        self.assertIn('<small>Propósito</small><p>Crear bienestar para todos.</p>', self.html)
        self.assertIn('<small>Misión</small><p>Hacer el bienestar personalizado universalmente accesible.</p>', self.html)
        self.assertIn('<small>Visión</small><p>Un mundo donde cada persona pueda vivir en bienestar — en movimiento.</p>', self.html)

    def test_presenta_los_valores(self):
        for dato in ('Lealtad', 'Confianza', 'Competitividad', 'Honestidad'):
            self.assertIn(dato, self.html, dato)

    def test_no_repite_afirmaciones_que_el_informe_no_respalda(self):
        for frase in ('secado rápido', 'protección solar', 'libre de irritaciones', 'pH equilibrado',
                      'repelencia sobresaliente', '13–18', 'ecológic', 'antimicrobian'):
            self.assertNotIn(frase, self.html, frase)

    def test_no_menciona_el_coach_la_beta_ni_la_historia_de_la_empresa(self):
        for dato in ('Coach', 'beta', 'Android', 'Friends N Gifts', 'Founder Institute', 'Detalle de los ensayos', 'Durabilidad medida'):
            self.assertNotIn(dato, self.html, dato)

    def test_no_menciona_resultados_de_laboratorio_propios(self):
        for dato in ('SENA', 'ISO/IEC 17025', 'Martindale', '12-10-24', 'id="laboratorio"', 'href="#laboratorio"'):
            self.assertNotIn(dato, self.html, dato)

    def test_el_eslogan_principal_es_wear_the_intelligence(self):
        self.assertIn('<h2>Wear the intelligence.</h2>', self.html)

    def test_el_indice_apunta_a_secciones_existentes(self):
        destinos = re.findall(r'<li><a href="#([a-z]+)">', self.html)
        self.assertTrue(destinos)
        for destino in destinos:
            self.assertIn(f'id="{destino}"', self.html, destino)


class TextoDelWelcomeTests(TestCase):
    def test_ya_no_menciona_un_producto_concreto(self):
        html = self.client.get(reverse('home')).content.decode()
        self.assertNotIn('X5', html)
        self.assertIn('Ropa deportiva con tecnología textil', html)


class AcercaDeTraducidaTests(TestCase):
    def tearDown(self):
        # LocaleMiddleware deja activo el idioma de la ultima peticion en el hilo.
        translation.activate('es')

    def test_se_sirve_en_ingles_y_portugues_sin_perder_citas_ni_referencias(self):
        esperado = {
            'en': ('About GoToGym', 'Graphene: one atom thick', 'View source', 'Four values that guide every decision.'),
            'pt': ('Sobre a GoToGym', 'Grafeno: um átomo de espessura', 'Ver fonte', 'Quatro valores que guiam cada decisão.'),
        }
        for idioma, frases in esperado.items():
            html = self.client.get(f'/{idioma}/acerca-de/').content.decode()
            for frase in frases:
                self.assertIn(frase, html, f'{idioma}: {frase}')
            citas = set(re.findall(r'href="#ref-(\d+)"', html))
            ids = set(re.findall(r'id="ref-(\d+)"', html))
            self.assertEqual(citas, ids, idioma)
            self.assertNotIn('Nuestra razón de movernos', html, idioma)

    def test_la_cifra_de_conductividad_usa_el_formato_de_cada_idioma(self):
        self.assertIn('4,840 – 5,300', self.client.get('/en/acerca-de/').content.decode())
        self.assertIn('4.840 – 5.300', self.client.get('/pt/acerca-de/').content.decode())
