"""Comando `generar_derivados_imagen`, aislado en una carpeta temporal: no
toca los derivados ni el manifiesto reales del proyecto."""
import json
import shutil
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from PIL import Image

from tienda import imagenes


class GenerarDerivadosTests(SimpleTestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix='gotogym-derivados-'))
        self.addCleanup(shutil.rmtree, self.base, True)
        self.catalogo = self.base / 'static' / 'product_media' / 'products'
        self.catalogo.mkdir(parents=True)
        self.medios = self.base / 'media'
        configuracion = override_settings(BASE_DIR=self.base, MEDIA_ROOT=self.medios)
        configuracion.enable()
        self.addCleanup(configuracion.disable)
        imagenes.limpiar_cache()
        self.addCleanup(imagenes.limpiar_cache)

    def _foto(self, ruta, ancho, alto=None):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (ancho, alto or ancho // 2), color=(20, 120, 200)).save(ruta, 'PNG')
        return ruta

    def _correr(self, *args):
        salida = StringIO()
        call_command('generar_derivados_imagen', *args, stdout=salida)
        return salida.getvalue()

    def _manifiesto(self):
        return json.loads(imagenes.ruta_manifiesto().read_text(encoding='utf-8'))

    def test_genera_derivados_solo_hasta_el_ancho_original_y_el_manifiesto(self):
        self._foto(self.catalogo / 'Camiseta Roja.png', 1000)
        salida = self._correr()

        manifiesto = self._manifiesto()
        clave = 'product_media/products/Camiseta Roja.png'
        self.assertIn(clave, manifiesto)
        registro = manifiesto[clave]
        self.assertEqual((registro['ancho'], registro['alto']), (1000, 500))
        # 1000 px: se generan 400, 640 y 960; 1280 y 1920 agrandarian.
        self.assertEqual(registro['formatos']['avif'], [400, 640, 960])
        self.assertEqual(registro['formatos']['webp'], [400, 640, 960])
        nombre = registro['nombre']
        self.assertTrue((imagenes.raiz_derivados() / f'{nombre}-640.avif').exists())
        self.assertTrue((imagenes.raiz_derivados() / f'{nombre}-960.webp').exists())
        self.assertFalse((imagenes.raiz_derivados() / f'{nombre}-1280.avif').exists())
        self.assertIn('1 imagenes en el manifiesto', salida)

    def test_una_imagen_mas_pequena_que_el_menor_ancho_genera_uno_solo(self):
        self._foto(self.catalogo / 'mini.png', 200)
        self._correr()
        registro = self._manifiesto()['product_media/products/mini.png']
        self.assertEqual(registro['formatos']['avif'], [200])
        self.assertEqual(registro['formatos']['webp'], [200])

    def test_es_idempotente_y_forzar_regenera(self):
        self._foto(self.catalogo / 'a.png', 700)
        self._correr()
        segunda = self._correr()
        self.assertIn('0 derivados nuevos', segunda)
        self.assertNotIn(' 0 ya al dia', segunda)
        forzada = self._correr('--forzar')
        self.assertIn('0 ya al dia', forzada)

    def test_ignora_archivos_que_no_son_imagenes(self):
        (self.catalogo / 'notas.txt').write_text('no soy una foto')
        self._foto(self.catalogo / 'b.png', 500)
        self._correr()
        self.assertEqual(list(self._manifiesto()), ['product_media/products/b.png'])

    def test_una_imagen_corrupta_se_avisa_y_no_detiene_el_proceso(self):
        (self.catalogo / 'rota.png').write_bytes(b'esto no es un png')
        self._foto(self.catalogo / 'buena.png', 500)
        salida = self._correr()
        self.assertIn('no se pudo procesar products/rota.png', salida)
        self.assertEqual(list(self._manifiesto()), ['product_media/products/buena.png'])

    def test_incluye_las_fotos_editoriales_de_media(self):
        self._foto(self.medios / 'products' / 'Imagenes Home' / 'Hero 1.png', 900)
        self._correr()
        self.assertIn('media/products/Imagenes Home/Hero 1.png', self._manifiesto())

    def test_sin_carpetas_de_origen_avisa_y_deja_un_manifiesto_vacio(self):
        shutil.rmtree(self.base / 'static' / 'product_media')
        salida = self._correr()
        self.assertIn('sin carpeta catalogo', salida)
        self.assertEqual(self._manifiesto(), {})
