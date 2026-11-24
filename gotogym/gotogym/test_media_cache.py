"""/media/ se sirve con cache publica de un dia."""
import shutil
from pathlib import Path

from django.conf import settings
from django.test import TestCase


class CacheDeMediaTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # La ruta de /media/ queda fijada con el MEDIA_ROOT con que arranco el
        # proceso: el archivo de prueba va ahi, en una carpeta propia.
        cls.carpeta = Path(settings.MEDIA_ROOT) / '_prueba_cache_media'
        cls.carpeta.mkdir(parents=True, exist_ok=True)
        (cls.carpeta / 'foto.txt').write_text('contenido', encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.carpeta, ignore_errors=True)
        super().tearDownClass()

    def _pedir(self, ruta, **extra):
        # La respuesta de un archivo es un flujo que mantiene el archivo abierto;
        # en Windows eso impide borrar la carpeta al terminar la clase.
        respuesta = self.client.get(ruta, **extra)
        self.addCleanup(respuesta.close)
        return respuesta

    def test_un_archivo_se_sirve_con_cache_publica_de_un_dia(self):
        respuesta = self._pedir('/media/_prueba_cache_media/foto.txt')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Cache-Control'], 'public, max-age=86400')

    def test_la_revalidacion_condicional_conserva_la_cache(self):
        primera = self._pedir('/media/_prueba_cache_media/foto.txt')
        segunda = self._pedir(
            '/media/_prueba_cache_media/foto.txt', HTTP_IF_MODIFIED_SINCE=primera['Last-Modified'],
        )
        self.assertEqual(segunda.status_code, 304)
        self.assertEqual(segunda['Cache-Control'], 'public, max-age=86400')

    def test_un_archivo_que_no_existe_no_se_cachea(self):
        respuesta = self._pedir('/media/_prueba_cache_media/no-existe.txt')
        self.assertEqual(respuesta.status_code, 404)
        self.assertNotIn('max-age=86400', respuesta.get('Cache-Control', ''))
