"""Banner de cookies y politica de cookies."""
import re
from pathlib import Path

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

RAIZ = Path(__file__).resolve().parents[1]


class BannerDeCookiesTests(TestCase):
    def test_todas_las_paginas_con_la_plantilla_base_incluyen_el_banner(self):
        for ruta in (reverse('home'), reverse('contacto'), reverse('tienda:producto_list'), reverse('commercial_login')):
            with self.subTest(ruta=ruta):
                html = self.client.get(ruta).content.decode()
                self.assertIn('id="gtg-cookies"', html)
                self.assertIn('css/cookie_banner.css', html)
                self.assertIn('js/cookies.js', html)

    def test_el_banner_nace_oculto_y_es_accesible(self):
        html = self.client.get(reverse('home')).content.decode()
        banner = re.search(r'<section id="gtg-cookies"[^>]*>', html).group(0)
        for atributo in ('role="dialog"', 'aria-labelledby="gtg-cookies-titulo"', 'aria-describedby="gtg-cookies-texto"', ' hidden'):
            self.assertIn(atributo, banner)

    def test_ofrece_aceptar_solo_necesarias_y_configurar(self):
        html = self.client.get(reverse('home')).content.decode()
        for control in ('data-cookies-aceptar', 'data-cookies-rechazar', 'data-cookies-configurar', 'data-cookies-guardar'):
            self.assertIn(control, html)

    def test_enlaza_la_politica_de_cookies(self):
        html = self.client.get(reverse('home')).content.decode()
        self.assertIn(f'href="{reverse("politica_cookies")}"', html)

    def test_el_pie_permite_reabrir_las_preferencias(self):
        html = self.client.get(reverse('acerca_de')).content.decode()
        self.assertIn('data-cookies-abrir', html)


class PoliticaDeCookiesTests(TestCase):
    def setUp(self):
        self.html = self.client.get(reverse('politica_cookies')).content.decode()

    def test_es_publica_y_esta_en_el_menu_legal(self):
        self.assertIn('Política de cookies', self.html)
        self.assertIn('href="{}" aria-current="page"'.format(reverse('politica_cookies')), self.html)

    def test_lista_las_cookies_reales_del_sitio(self):
        for nombre in ('sessionid', 'csrftoken', 'django_language', 'gtg_cookies', 'ARRAffinity', 'gtg_atribucion'):
            self.assertIn(nombre, self.html)

    def test_declara_lo_que_no_hace(self):
        self.assertIn('No usamos cookies de publicidad', self.html)

    def test_permite_abrir_las_preferencias(self):
        self.assertIn('data-cookies-abrir', self.html)


class CookiesDelProyectoCoincidenConLaPoliticaTests(SimpleTestCase):
    """Lo que el codigo guarda en el navegador tiene que estar en la politica."""

    def test_el_script_de_analitica_solo_usa_el_almacenamiento_declarado(self):
        js = (RAIZ / 'static' / 'js' / 'analytics.js').read_text(encoding='utf-8')
        claves = set(re.findall(r"(?:session|local)Storage\.(?:get|set)Item\('([^']+)'", js))
        self.assertEqual(claves, {'gtg_atribucion'})

    def test_el_javascript_del_sitio_no_escribe_otras_cookies(self):
        for archivo in (RAIZ / 'static' / 'js').glob('*.js'):
            texto = archivo.read_text(encoding='utf-8')
            for asignacion in re.findall(r"document\.cookie\s*=\s*([^;]+);", texto):
                self.assertIn('NOMBRE', asignacion, f'{archivo.name}: cookie no declarada en la politica')

    def test_el_sitio_no_carga_scripts_ni_estilos_de_terceros(self):
        for plantilla in (RAIZ / 'gotogym' / 'templates').rglob('*.html'):
            texto = plantilla.read_text(encoding='utf-8')
            externos = re.findall(r'<(?:script|link)[^>]+(?:src|href)="https?://', texto)
            self.assertEqual(externos, [], plantilla.name)
