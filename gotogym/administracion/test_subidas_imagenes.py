"""Fotos que sube el panel (`product_media_add`): tamano, formato real
comprobado con Pillow, dimensiones y nombre de archivo."""
import io
import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from products.models import Brand, Product, ProductCategory, ProductMedia

from .forms import MAX_BYTES_IMAGEN, MAX_LADO_IMAGEN

_MEDIA_ROOT_DE_PRUEBA = tempfile.mkdtemp(prefix='gotogym-test-subidas-')


def _bytes_de_imagen(formato='PNG', tamano=(1, 1)):
    buffer = io.BytesIO()
    Image.new('RGB', tamano, color='white').save(buffer, format=formato)
    return buffer.getvalue()


@override_settings(MEDIA_ROOT=_MEDIA_ROOT_DE_PRUEBA)
class SubidaDeFotosTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_MEDIA_ROOT_DE_PRUEBA, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.producto = Product.objects.create(
            name='Producto subidas', category=ProductCategory.objects.create(name='Categoria subidas'),
            brand=Brand.objects.create(name='Marca subidas'), base_price=Decimal('90000.0000'), stock=0,
        )
        cls.staff = get_user_model().objects.create_superuser(
            email='root-subidas@example.com', username='root-subidas@example.com', password='x',
        )

    def setUp(self):
        self.client.force_login(self.staff)

    def _subir(self, nombre, contenido, tipo='image/png'):
        archivo = SimpleUploadedFile(nombre, contenido, content_type=tipo)
        return self.client.post(reverse('admin_product_media_add', args=[self.producto.pk]), {'image': archivo})

    def _quedaron(self):
        return ProductMedia.objects.filter(product=self.producto).count()

    def test_una_foto_valida_se_guarda(self):
        self._subir('foto.png', _bytes_de_imagen())
        self.assertEqual(self._quedaron(), 1)

    def test_un_texto_renombrado_a_jpg_se_rechaza_aunque_declare_ser_jpeg(self):
        self._subir('foto.jpg', b'<?php echo 1; ?> esto no es una imagen', tipo='image/jpeg')
        self.assertEqual(self._quedaron(), 0)

    def test_un_html_con_cabecera_de_imagen_se_rechaza(self):
        self._subir('foto.png', b'\x89PNG\r\n\x1a\n<script>alert(1)</script>')
        self.assertEqual(self._quedaron(), 0)

    def test_una_imagen_real_de_mas_de_6000_px_se_rechaza(self):
        # 1 px de alto: el archivo pesa poco, lo que sobra son las dimensiones.
        contenido = _bytes_de_imagen('PNG', (MAX_LADO_IMAGEN + 1, 1))
        self.assertLess(len(contenido), MAX_BYTES_IMAGEN)
        self._subir('ancha.png', contenido)
        self.assertEqual(self._quedaron(), 0)

    def test_una_imagen_de_exactamente_6000_px_se_acepta(self):
        self._subir('limite.png', _bytes_de_imagen('PNG', (MAX_LADO_IMAGEN, 1)))
        self.assertEqual(self._quedaron(), 1)

    def test_un_archivo_de_mas_de_5_mb_se_rechaza(self):
        self._subir('pesada.png', _bytes_de_imagen() + b'\0' * (MAX_BYTES_IMAGEN + 1))
        self.assertEqual(self._quedaron(), 0)

    def test_una_foto_valida_con_nombre_de_pagina_o_script_se_rechaza(self):
        # Sin esto el archivo se serviria desde /media/ como HTML o SVG del propio sitio.
        for nombre in ('foto.html', 'foto.svg', 'foto.js', 'foto.xml', 'foto', 'foto.png.html'):
            with self.subTest(nombre=nombre):
                self._subir(nombre, _bytes_de_imagen())
                self.assertEqual(self._quedaron(), 0)

    def test_acepta_jpg_jpeg_y_webp_con_cualquier_mayuscula(self):
        self._subir('a.JPG', _bytes_de_imagen('JPEG'), tipo='image/jpeg')
        self._subir('b.jpeg', _bytes_de_imagen('JPEG'), tipo='image/jpeg')
        self._subir('c.WebP', _bytes_de_imagen('WEBP'), tipo='image/webp')
        self.assertEqual(self._quedaron(), 3)

    def test_un_formato_real_no_permitido_se_rechaza_aunque_se_llame_png(self):
        self._subir('animada.png', _bytes_de_imagen('GIF'), tipo='image/png')
        self.assertEqual(self._quedaron(), 0)
