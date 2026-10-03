import re
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from .journal_content import POSTS
from .models import Category, Post
from .templatetags.blog_extras import post_body


class PostBodyTests(TestCase):
    def test_subtitulos_listas_y_parrafos(self):
        html = post_body('Intro con **fuerza**.\n\n## Un subtitulo\n\n- uno\n- dos\n\nLinea A\nLinea B')
        self.assertIn('<p>Intro con <strong>fuerza</strong>.</p>', html)
        self.assertIn('<h2>Un subtitulo</h2>', html)
        self.assertIn('<ul><li>uno</li><li>dos</li></ul>', html)
        self.assertIn('<p>Linea A<br>Linea B</p>', html)

    def test_las_citas_enlazan_a_la_lista_de_referencias(self):
        html = post_body('Dato medido [3].')
        self.assertIn('<a href="#ref-3" aria-label="Referencia 3">[3]</a>', html)

    def test_no_deja_pasar_html(self):
        html = post_body('<script>alert(1)</script>\n\n## <b>x</b>')
        self.assertNotIn('<script>', html)
        self.assertNotIn('<b>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_contenido_vacio(self):
        self.assertEqual(post_body(''), '')
        self.assertEqual(post_body(None), '')


class ReferenciasDeUnaEntradaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        autor = get_user_model().objects.create_user(
            email='autor@example.com', username='autor@example.com', password='secret123',
        )
        cls.post = Post.objects.create(
            title='Con referencias', author=autor, content='Texto [1].',
            references='Autor (2020). Titulo. Revista. | https://example.org/a\n\nSolo texto sin enlace',
        )

    def test_separa_texto_y_enlace(self):
        self.assertEqual(self.post.reference_items, [
            {'text': 'Autor (2020). Titulo. Revista.', 'url': 'https://example.org/a'},
            {'text': 'Solo texto sin enlace', 'url': ''},
        ])

    def test_el_detalle_muestra_la_lista_con_anclas(self):
        html = self.client.get(reverse('blog:post_detail', args=[self.post.slug])).content.decode()
        self.assertIn('id="ref-1"', html)
        self.assertIn('id="ref-2"', html)
        self.assertIn('href="https://example.org/a"', html)
        self.assertIn('href="#ref-1"', html)

    def test_una_entrada_sin_referencias_no_muestra_la_seccion(self):
        self.post.references = ''
        self.post.save()
        html = self.client.get(reverse('blog:post_detail', args=[self.post.slug])).content.decode()
        self.assertNotIn('editorial-references', html)


class ContenidoDelJournalTests(TestCase):
    """Las entradas incluidas deben ser internamente consistentes: toda cita
    [n] apunta a una referencia que existe, y toda referencia trae enlace."""

    def test_cada_cita_tiene_su_referencia(self):
        for datos in POSTS:
            referencias = [r for r in datos['references'].splitlines() if r.strip()]
            citadas = {int(n) for n in re.findall(r'\[(\d{1,2})\]', datos['content'])}
            self.assertTrue(citadas, datos['slug'])
            self.assertLessEqual(max(citadas), len(referencias), datos['slug'])

    def test_cada_referencia_se_cita_en_el_texto(self):
        for datos in POSTS:
            referencias = [r for r in datos['references'].splitlines() if r.strip()]
            citadas = {int(n) for n in re.findall(r'\[(\d{1,2})\]', datos['content'])}
            self.assertEqual(citadas, set(range(1, len(referencias) + 1)), datos['slug'])

    def test_cada_referencia_trae_un_enlace_https(self):
        for datos in POSTS:
            for linea in datos['references'].splitlines():
                _, _, url = linea.partition('|')
                self.assertTrue(url.strip().startswith('https://'), (datos['slug'], linea[:60]))

    def test_los_slugs_son_unicos(self):
        slugs = [datos['slug'] for datos in POSTS]
        self.assertEqual(len(slugs), len(set(slugs)))


class SeedJournalTests(TestCase):
    def _admin(self):
        return get_user_model().objects.create_superuser(
            email='root@example.com', username='root@example.com', password='secret123',
        )

    def _admin_posterior(self):
        return get_user_model().objects.create_superuser(
            email='otro-root@example.com', username='otro-root@example.com', password='secret123',
        )

    def _correr(self, *args):
        salida = StringIO()
        call_command('seed_journal', *args, stdout=salida)
        return salida.getvalue()

    def test_crea_las_entradas_publicadas_con_su_categoria(self):
        self._admin()
        self._correr()
        self.assertEqual(Post.objects.count(), len(POSTS))
        self.assertFalse(Post.objects.filter(is_published=False).exists())
        self.assertTrue(Category.objects.filter(name='Materiales').exists())

    def test_por_defecto_el_autor_es_el_primer_superusuario(self):
        primero = self._admin()
        self._admin_posterior()
        self._correr()
        self.assertEqual(set(Post.objects.values_list('author_id', flat=True)), {primero.pk})

    def test_permite_elegir_el_autor(self):
        admin = self._admin()
        self._correr('--author', admin.email)
        self.assertEqual(set(Post.objects.values_list('author__email', flat=True)), {admin.email})

    def test_un_autor_inexistente_falla_con_mensaje_claro(self):
        with self.assertRaises(CommandError):
            self._correr('--author', 'nadie@example.com')

    def test_es_idempotente(self):
        self._admin()
        self._correr()
        self._correr()
        self.assertEqual(Post.objects.count(), len(POSTS))

    def test_actualiza_el_contenido_si_cambio(self):
        self._admin()
        self._correr()
        Post.objects.filter(slug=POSTS[0]['slug']).update(content='alterado')
        self._correr()
        self.assertEqual(Post.objects.get(slug=POSTS[0]['slug']).content, POSTS[0]['content'])

    def test_solo_faltantes_no_pisa_lo_ya_cargado_ni_sus_ediciones(self):
        self._admin()
        self._correr()
        Post.objects.filter(slug=POSTS[0]['slug']).update(content='editado a mano')
        salida = self._correr('--solo-faltantes')
        self.assertEqual(Post.objects.get(slug=POSTS[0]['slug']).content, 'editado a mano')
        self.assertIn(f'{len(POSTS)} sin cambios', salida)

    def test_solo_faltantes_crea_las_que_no_existen(self):
        self._admin()
        self._correr()
        Post.objects.filter(slug=POSTS[1]['slug']).delete()
        self._correr('--solo-faltantes')
        self.assertEqual(Post.objects.count(), len(POSTS))

    def test_sin_autor_disponible_falla_con_mensaje_claro(self):
        get_user_model().objects.all().delete()
        with self.assertRaises(CommandError):
            self._correr()

    def test_las_entradas_se_ven_en_el_journal_y_en_su_detalle(self):
        self._admin()
        self._correr()
        listado = self.client.get(reverse('blog:post_list'))
        self.assertContains(listado, POSTS[0]['title'])
        detalle = self.client.get(reverse('blog:post_detail', args=[POSTS[0]['slug']]))
        self.assertEqual(detalle.status_code, 200)
        self.assertContains(detalle, 'id="ref-1"')
        self.assertContains(detalle, '<h2>')
