"""Selector de idioma ES / EN y coherencia de los terminos del cliente con las politicas."""
import re

from django.test import TestCase
from django.urls import reverse
from django.utils import translation


class SelectorDeIdiomaTests(TestCase):
    def tearDown(self):
        # LocaleMiddleware deja activo el idioma de la ultima peticion en el hilo.
        translation.activate('es')

    def test_aparece_en_el_menu_el_panel_movil_y_el_pie(self):
        html = self.client.get(reverse('home')).content.decode()
        for variante in ('menu', 'movil', 'pie'):
            self.assertIn(f'gtg-lang--{variante}', html)

    def test_ofrece_espanol_e_ingles_y_marca_el_actual(self):
        html = self.client.get('/es/').content.decode()
        self.assertRegex(html, r'value="es"[^>]*aria-current="true"')
        self.assertNotRegex(html, r'value="en"[^>]*aria-current="true"')
        html_en = self.client.get('/en/').content.decode()
        self.assertRegex(html_en, r'value="en"[^>]*aria-current="true"')

    def test_cada_boton_lleva_la_pagina_actual_ya_traducida(self):
        html = self.client.get('/es/politica-cookies/?x=1').content.decode()
        self.assertIn('name="next" value="/es/politica-cookies/?x=1"', html)
        self.assertIn('name="next" value="/en/politica-cookies/?x=1"', html)

    def test_desde_la_version_en_ingles_se_puede_volver_a_espanol(self):
        # El idioma activo al enviar el formulario puede no ser el de la pagina:
        # por eso la direccion llega ya traducida.
        html = self.client.get('/en/politica-cookies/').content.decode()
        self.assertIn('name="next" value="/es/politica-cookies/"', html)
        self.assertIn('name="next" value="/en/politica-cookies/"', html)

    def test_cambiar_a_ingles_lleva_a_la_pagina_en_ingles_y_recuerda_la_eleccion(self):
        respuesta = self.client.post(reverse('set_language'), {'language': 'en', 'next': '/en/tienda/'})
        self.assertRedirects(respuesta, '/en/tienda/', fetch_redirect_response=False)
        self.assertEqual(self.client.cookies['django_language'].value, 'en')

    def test_cambiar_a_espanol_desde_ingles_aunque_no_haya_cookie(self):
        respuesta = self.client.post(reverse('set_language'), {'language': 'es', 'next': '/es/acerca-de/'})
        self.assertRedirects(respuesta, '/es/acerca-de/', fetch_redirect_response=False)
        self.assertEqual(self.client.cookies['django_language'].value, 'es')

    def test_la_pagina_en_ingles_muestra_el_banner_y_el_selector_traducidos(self):
        html = self.client.get('/en/').content.decode()
        self.assertIn('Cookies at GoToGym', html)
        self.assertIn('Reject', html)
        self.assertIn('aria-label="Language"', html)


class TerminosDelClienteCoincidenConLasPoliticasTests(TestCase):
    def setUp(self):
        self.html = self.client.get(reverse('terminos')).content.decode()
        self.texto = re.sub(r'<[^>]+>', ' ', self.html)

    def test_no_dice_que_las_ventas_son_finales(self):
        self.assertNotIn('ventas son finales', self.texto)

    def test_remite_a_cambios_devoluciones_y_garantia_con_el_retracto(self):
        self.assertIn('Cambios, Devoluciones y Garantía', self.texto)
        self.assertIn('5 días hábiles', self.texto)

    def test_el_unico_medio_de_pago_es_mercado_pago(self):
        self.assertIn('Mercado Pago', self.texto)
        self.assertNotIn('PayPal', self.texto)
        self.assertNotIn('Transferencia Bancaria', self.texto)

    def test_ya_no_ofrece_productos_personalizados(self):
        self.assertNotIn('productos físicos personalizados', self.texto)
        self.assertNotIn('Personalización de Productos', self.texto)

    def test_los_derechos_de_datos_van_al_correo_de_privacidad(self):
        self.assertIn('privacy@gotogym.store', self.texto)

    def test_no_lleva_un_ano_viejo(self):
        self.assertNotIn('2025', self.texto)
