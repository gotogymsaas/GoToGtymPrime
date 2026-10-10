"""Material de marca: lo sube y administra el equipo desde el panel de
administracion, y solo lo descargan afiliados activos."""
import shutil
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from .models import EstadoAfiliado, PerfilAfiliado, RecursoMarca
from .services import deactivate_afiliado
from .tests import AfiliadoTestBase

CONTENIDO = b'\x89PNG\r\n\x1a\n-contenido-de-prueba'


class _ConRecursos(AfiliadoTestBase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(settings.RECURSOS_AFILIADOS_ROOT, ignore_errors=True)

    def _subir(self, nombre='logo.png', contenido=CONTENIDO, **datos):
        archivo = SimpleUploadedFile(nombre, contenido, content_type='application/octet-stream')
        return self.client.post(reverse('admin_recurso_new'), {
            'title': 'Logo oficial', 'description': 'Fondo transparente', 'order': '1', 'is_active': 'on',
            'file': archivo, **datos,
        })


class AdministracionDeRecursosTests(_ConRecursos):
    def setUp(self):
        super().setUp()
        self._dar_permisos_de_admin(self.admin)
        self.client.force_login(self.admin)

    def test_el_admin_sube_un_recurso(self):
        respuesta = self._subir()
        self.assertRedirects(respuesta, reverse('admin_recursos'), fetch_redirect_response=False)
        recurso = RecursoMarca.objects.get()
        self.assertEqual(recurso.title, 'Logo oficial')
        self.assertEqual(recurso.extension, 'PNG')
        self.assertContains(self.client.get(reverse('admin_recursos')), 'Logo oficial')

    def test_el_archivo_no_queda_bajo_la_carpeta_publica_de_medios(self):
        self._subir()
        ruta = Path(RecursoMarca.objects.get().file.path).resolve()
        self.assertTrue(ruta.is_file())
        self.assertNotIn(Path(settings.MEDIA_ROOT).resolve(), ruta.parents)
        self.assertIn(Path(settings.RECURSOS_AFILIADOS_ROOT).resolve(), ruta.parents)

    def test_rechaza_formatos_que_podrian_ejecutarse(self):
        for nombre in ('virus.exe', 'pagina.html', 'imagen.svg', 'script.js', 'sin_extension'):
            with self.subTest(nombre=nombre):
                respuesta = self._subir(nombre)
                self.assertEqual(respuesta.status_code, 200)
                self.assertIn('file', respuesta.context['form'].errors)
        self.assertFalse(RecursoMarca.objects.exists())

    def test_acepta_los_formatos_permitidos(self):
        for nombre in ('a.png', 'b.JPG', 'c.jpeg', 'd.webp', 'e.pdf', 'f.zip', 'g.mp4'):
            with self.subTest(nombre=nombre):
                self._subir(nombre, title=nombre)
        self.assertEqual(RecursoMarca.objects.count(), 7)

    def test_rechaza_archivos_de_mas_de_25_mb(self):
        # Se pide por nombre: `administracion` es una app de nivel superior.
        with patch('administracion.forms.TAMANO_MAXIMO_DE_RECURSO', 10):
            respuesta = self._subir(contenido=b'x' * 11)
        self.assertIn('25 MB', ' '.join(respuesta.context['form'].errors['file']))

    def test_editar_sin_cambiar_el_archivo_lo_conserva(self):
        self._subir()
        recurso = RecursoMarca.objects.get()
        nombre = recurso.file.name
        self.client.post(reverse('admin_recurso_edit', args=[recurso.pk]), {
            'title': 'Logo nuevo', 'description': '', 'order': '2',
        })
        recurso.refresh_from_db()
        self.assertEqual(recurso.title, 'Logo nuevo')
        self.assertEqual(recurso.file.name, nombre)
        self.assertFalse(recurso.is_active)

    def test_eliminar_borra_el_registro_y_el_archivo(self):
        self._subir()
        recurso = RecursoMarca.objects.get()
        ruta = Path(recurso.file.path)
        self.client.post(reverse('admin_recurso_delete', args=[recurso.pk]))
        self.assertFalse(RecursoMarca.objects.exists())
        self.assertFalse(ruta.exists())

    def test_sin_permisos_no_se_puede_subir_ni_eliminar(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group

        self._subir()
        recurso = RecursoMarca.objects.get()
        intermedio = get_user_model().objects.create_user(
            email='intermedio-recursos@example.com', username='intermedio-recursos@example.com',
            password='secret123', is_staff=True,
        )
        intermedio.groups.add(Group.objects.create(name='Grupo sin permisos de recursos'))
        self.client.force_login(intermedio)

        self._subir(title='Otro')
        self.client.post(reverse('admin_recurso_delete', args=[recurso.pk]))

        self.assertEqual(RecursoMarca.objects.count(), 1)

    def test_un_cliente_sin_staff_no_entra_al_panel_de_recursos(self):
        self.client.force_login(self.comprador)
        self.assertEqual(self.client.get(reverse('admin_recursos')).status_code, 302)


class DescargaDeRecursosTests(_ConRecursos):
    def setUp(self):
        super().setUp()
        self._dar_permisos_de_admin(self.admin)
        self.client.force_login(self.admin)
        self._subir()
        self.recurso = RecursoMarca.objects.get()
        self.url = reverse('afiliado_recurso_descargar', args=[self.recurso.pk])
        self.perfil = self._crear_perfil_aprobado()
        self.client.force_login(self.afiliado_user)

    def test_un_afiliado_activo_lo_ve_y_lo_descarga_como_adjunto(self):
        self.assertContains(self.client.get(reverse('afiliado_recursos')), 'Logo oficial')
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('attachment', respuesta['Content-Disposition'])
        self.assertEqual(b''.join(respuesta.streaming_content), CONTENIDO)

    def test_el_enlace_de_descarga_aparece_en_la_pagina_de_recursos(self):
        self.assertContains(self.client.get(reverse('afiliado_recursos')), self.url)

    def test_un_recurso_oculto_no_se_lista_ni_se_descarga(self):
        RecursoMarca.objects.filter(pk=self.recurso.pk).update(is_active=False)
        self.assertNotContains(self.client.get(reverse('afiliado_recursos')), 'Logo oficial')
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_quien_no_es_afiliado_activo_no_descarga(self):
        PerfilAfiliado.objects.filter(pk=self.perfil.pk).update(status=EstadoAfiliado.PENDING)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        PerfilAfiliado.objects.filter(pk=self.perfil.pk).update(status=EstadoAfiliado.APPROVED)
        deactivate_afiliado(PerfilAfiliado.objects.get(pk=self.perfil.pk))
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_un_usuario_cualquiera_y_un_anonimo_no_descargan(self):
        self.client.force_login(self.comprador)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_la_ruta_publica_de_medios_no_sirve_el_archivo(self):
        nombre = self.recurso.file.name.rsplit('/', 1)[-1]
        self.client.logout()
        for ruta in (f'/media/recursos/{nombre}', f'/media/{self.recurso.file.name}'):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 404)

    def test_sin_recursos_la_pagina_indica_a_quien_escribir(self):
        RecursoMarca.objects.all().delete()
        self.assertContains(self.client.get(reverse('afiliado_recursos')), 'support@gotogym.store')

    def test_la_pagina_trae_la_guia_de_contenido(self):
        html = self.client.get(reverse('afiliado_recursos')).content.decode()
        for texto in ('#GoToGym', '#Publicidad', '#Ad', self.perfil.referral_code, 'Ejemplo no permitido'):
            with self.subTest(texto=texto):
                self.assertIn(texto, html)
