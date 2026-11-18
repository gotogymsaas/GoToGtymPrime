"""Comando que propone atributos del catalogo a partir de la foto del producto."""
import io
import shutil
import tempfile
from unittest import mock

from django.core.files.base import ContentFile
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from products.models import ProductMedia

from . import coach_client, vision
from .test_imagen import foto
from .test_utilidades import aislar_catalogo, crear_producto


class ProponerAtributosTests(TestCase):
    def setUp(self):
        aislar_catalogo()
        carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, carpeta, ignore_errors=True)
        ajustes = override_settings(MEDIA_ROOT=carpeta)
        ajustes.enable()
        self.addCleanup(ajustes.disable)
        self.producto, _ = crear_producto('X5 Generation', [('M', 'UNICO', 1)])
        ProductMedia.objects.create(
            product=self.producto, image=ContentFile(foto(), name='x5.jpg'), is_primary=True)
        self.coach = mock.Mock()
        self.coach.describir.return_value = vision.Descripcion(
            ok=True, prenda=True, confianza=0.7,
            atributos={'garment_type': 'conjunto', 'fit': 'ajustado', 'colors': ['negro']})
        parche = mock.patch.object(coach_client, 'obtener_cliente', return_value=self.coach)
        parche.start()
        self.addCleanup(parche.stop)

    def _correr(self, *argumentos):
        salida = io.StringIO()
        call_command('vendedor_proponer_atributos', *argumentos, '--producto', str(self.producto.id), stdout=salida)
        self.producto.refresh_from_db()
        return salida.getvalue()

    def test_sin_aplicar_solo_muestra(self):
        salida = self._correr()

        self.assertIn('garment_type=conjunto', salida)
        self.assertEqual(self.producto.garment_type, '')
        self.assertEqual(self.coach.describir.call_args.args[0]['purpose'], 'catalog_attributes')

    def test_aplicar_llena_los_vacios_y_pide_revision(self):
        self._correr('--aplicar')

        self.assertEqual((self.producto.garment_type, self.producto.fit), ('conjunto', 'ajustado'))
        self.assertEqual(self.producto.visual_attributes_origin, 'ia')

    def test_nunca_cambia_lo_que_ya_tiene(self):
        self.producto.garment_type = 'top'
        self.producto.save()

        self._correr('--aplicar')

        self.assertEqual((self.producto.garment_type, self.producto.fit), ('top', 'ajustado'))

    def test_sin_coach_falla_con_un_mensaje_claro(self):
        with mock.patch.object(coach_client, 'obtener_cliente', return_value=None), \
                self.assertRaisesMessage(CommandError, 'No hay Coach configurado'):
            call_command('vendedor_proponer_atributos', stdout=io.StringIO())
