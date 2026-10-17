"""`previsualizar_correos`: genera todos los correos con datos de muestra y no deja nada en la base."""
import tempfile
from io import StringIO
from pathlib import Path

from afiliados.models import PerfilAfiliado
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from orders.models import Order


class PrevisualizarCorreosTests(TestCase):
    def _generar(self, **opciones):
        carpeta = tempfile.mkdtemp()
        call_command('previsualizar_correos', carpeta=carpeta, stdout=StringIO(), **opciones)
        return Path(carpeta)

    def test_escribe_un_html_y_un_texto_por_cada_correo_y_un_indice(self):
        carpeta = self._generar()
        htmls = sorted(p.name for p in carpeta.glob('[0-9]*.html'))
        textos = sorted(p.name for p in carpeta.glob('[0-9]*.txt'))
        self.assertGreaterEqual(len(htmls), 15)  # pedido (5), contrasena (1) y afiliados (10)
        self.assertEqual([n[:-5] for n in htmls], [n[:-4] for n in textos])
        indice = (carpeta / 'index.html').read_text(encoding='utf-8')
        for nombre in htmls:
            self.assertIn(f'href="{nombre}"', indice)
        for nombre in htmls:
            self.assertIn('<!DOCTYPE html>', (carpeta / nombre).read_text(encoding='utf-8'))

    def test_no_deja_datos_en_la_base_ni_correos_pendientes(self):
        usuarios = get_user_model().objects.count()
        self._generar()
        self.assertEqual(get_user_model().objects.count(), usuarios)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(PerfilAfiliado.objects.count(), 0)
        self.assertEqual(mail.outbox, [])

    def test_las_imagenes_del_sitio_apuntan_a_archivos_locales(self):
        carpeta = self._generar()
        html = (carpeta / '01.html').read_text(encoding='utf-8')
        self.assertIn('file:///', html)
        self.assertNotIn('https://gotogym.store/static/', html)

    def test_en_ingles_los_correos_del_pedido_salen_en_ingles(self):
        carpeta = self._generar(idioma='en')
        self.assertIn('We received your order', (carpeta / '01.html').read_text(encoding='utf-8'))
