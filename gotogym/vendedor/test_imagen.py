"""Preparacion de la foto: validar, reducir y quitar metadatos sin guardarla."""
import io

from django.test import SimpleTestCase
from PIL import Image

from . import imagen


def foto(formato='JPEG', tamano=(800, 600), color=(20, 60, 200), modo='RGB', **guardar):
    salida = io.BytesIO()
    Image.new(modo, tamano, color).save(salida, format=formato, **guardar)
    return salida.getvalue()


class PrepararTests(SimpleTestCase):
    def test_reduce_a_1024_y_sale_en_jpeg(self):
        preparada = imagen.preparar(foto(tamano=(4000, 3000)))

        self.assertEqual((preparada.ancho, preparada.alto), (1024, 768))
        self.assertEqual(preparada.media_type, 'image/jpeg')
        self.assertLessEqual(len(preparada.datos), imagen.MAX_BYTES_SALIDA)
        self.assertEqual(Image.open(io.BytesIO(preparada.datos)).format, 'JPEG')

    def test_quita_los_metadatos_y_aplica_la_orientacion(self):
        exif = Image.Exif()
        exif[0x0112] = 6        # Orientacion: girar 90 grados
        exif[0x010F] = 'Telefono de prueba'
        original = foto(tamano=(400, 200), exif=exif.tobytes())

        preparada = imagen.preparar(original)
        resultado = Image.open(io.BytesIO(preparada.datos))

        self.assertEqual(resultado.size, (200, 400))  # vertical, como se tomo
        self.assertEqual(dict(resultado.getexif()), {})

    def test_png_con_transparencia_queda_sobre_blanco(self):
        preparada = imagen.preparar(foto('PNG', (200, 200), (0, 0, 0, 0), modo='RGBA'))

        pixel = Image.open(io.BytesIO(preparada.datos)).getpixel((100, 100))
        self.assertTrue(all(canal > 240 for canal in pixel))

    def test_acepta_webp(self):
        self.assertEqual(imagen.preparar(foto('WEBP')).media_type, 'image/jpeg')

    def test_rechaza_lo_que_no_es_una_foto_permitida(self):
        casos = {
            'vacia': b'',
            'formato': b'esto no es una imagen',
            'gif': foto('GIF'),
            'pequena': foto(tamano=(20, 20)),
        }
        esperado = {'vacia': 'vacia', 'formato': 'formato', 'gif': 'formato', 'pequena': 'dimensiones'}
        for nombre, datos in casos.items():
            with self.subTest(caso=nombre), self.assertRaises(imagen.ImagenInvalida) as error:
                imagen.preparar(datos)
            self.assertEqual(error.exception.codigo, esperado[nombre])

    def test_rechaza_un_archivo_mas_grande_que_el_tope(self):
        with self.assertRaises(imagen.ImagenInvalida) as error:
            imagen.preparar(b'0' * (imagen.MAX_BYTES_SUBIDA + 1))
        self.assertEqual(error.exception.codigo, 'grande')

    def test_rechaza_una_imagen_de_demasiados_pixeles(self):
        # Pocos bytes, muchos pixeles: se rechaza antes de decodificarla.
        datos = foto('PNG', (8000, 6000), (255, 255, 255))
        with self.assertRaises(imagen.ImagenInvalida) as error:
            imagen.preparar(datos)
        self.assertEqual(error.exception.codigo, 'dimensiones')


class ColorDominanteTests(SimpleTestCase):
    def test_familias_basicas(self):
        casos = {
            (10, 10, 10): 'negro', (250, 250, 250): 'blanco', (128, 128, 128): 'gris',
            (200, 20, 20): 'rojo', (20, 160, 40): 'verde', (30, 60, 200): 'azul',
            (240, 140, 20): 'naranja', (230, 210, 30): 'amarillo', (120, 40, 180): 'morado',
            (230, 80, 160): 'rosa',
        }
        for rgb, familia in casos.items():
            with self.subTest(rgb=rgb):
                self.assertEqual(imagen.familia_de_rgb(*rgb), familia)

    def test_color_del_centro_de_la_foto(self):
        self.assertEqual(imagen.color_dominante(foto(color=(30, 60, 200))), 'azul')
