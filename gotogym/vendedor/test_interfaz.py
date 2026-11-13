"""Interfaz del asistente: boton, panel y reglas que el JavaScript y el CSS no
deben romper."""
import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

JS = Path(settings.BASE_DIR) / 'static' / 'js' / 'vendedor.js'
CSS = Path(settings.BASE_DIR) / 'static' / 'css' / 'vendedor.css'
PLANTILLA = Path(settings.BASE_DIR) / 'gotogym' / 'templates' / 'partials' / '_vendedor_panel.html'


class _Nodos(HTMLParser):
    """Recoge las etiquetas con sus atributos, en orden."""

    def __init__(self):
        super().__init__()
        self.etiquetas = []

    def handle_starttag(self, etiqueta, atributos):
        self.etiquetas.append((etiqueta, dict(atributos)))


def _nodos(html):
    parser = _Nodos()
    parser.feed(html)
    return parser.etiquetas


def _sin_comentarios(codigo):
    """El JavaScript sin comentarios: las reglas se comprueban sobre el codigo,
    no sobre lo que los comentarios dicen que no se hace."""
    sin_bloques = re.sub(r'/\*.*?\*/', '', codigo, flags=re.S)
    return re.sub(r'(?m)^\s*//.*$|(?<=\s)//.*$', '', sin_bloques)


def _con_atributo(html, atributo):
    return [(e, a) for e, a in _nodos(html) if atributo in a]


@override_settings(VENDEDOR_ENABLED=True, VENDEDOR_ROLLOUT_PERCENT=100)
class MarcadoTests(TestCase):
    def _html(self, url=None, idioma='es'):
        respuesta = self.client.get(url or f'/{idioma}/')
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.content.decode()

    def test_el_boton_abre_las_acciones_de_la_barra_antes_del_idioma(self):
        html = self._html()
        acciones = html[html.index('class="gtg-nav-actions"'):]
        boton = acciones.index('class="gtg-vendedor-toggle"')

        self.assertLess(boton, acciones.index('gtg-lang--menu'))
        # La barra de escritorio ya no lleva buscador: el Coach ocupa ese papel.
        self.assertNotIn('gtg-nav-search', acciones.split('</nav>')[0])

    def test_el_boton_muestra_el_orbe_el_nombre_y_la_etiqueta_ia(self):
        html = self._html()
        boton = html[html.index('class="gtg-vendedor-toggle"'):]
        boton = boton[:boton.index('</button>')]

        self.assertIn('coach-orb', boton)
        self.assertIn('>Quantum Coach<', boton)
        self.assertRegex(boton, r'gtg-vendedor-toggle__badge[^>]*>IA<')

    def test_el_boton_es_accesible_y_nace_oculto(self):
        html = self._html()
        botones = [a for e, a in _con_atributo(html, 'data-vendedor-toggle') if e == 'button']

        self.assertEqual(len(botones), 2)  # barra y menu movil
        for boton in botones:
            with self.subTest(origen=boton.get('data-track-origen')):
                self.assertEqual(boton['type'], 'button')
                self.assertEqual(boton['aria-expanded'], 'false')
                self.assertEqual(boton['aria-controls'], 'vendedor-panel')
                self.assertEqual(boton['aria-haspopup'], 'dialog')
                self.assertIn('hidden', boton)  # sin JavaScript no hay control muerto
                self.assertEqual(boton['data-track'], 'vendedor_open')

    def test_el_boton_de_la_barra_tiene_nombre_accesible(self):
        html = self._html()
        barra = next(a for e, a in _con_atributo(html, 'data-vendedor-toggle') if 'aria-label' in a)

        self.assertEqual(barra['aria-label'], 'Abrir Quantum Coach, la IA de GoToGym')
        # El nombre accesible contiene el texto visible ("Coach").
        self.assertIn('Coach', barra['aria-label'])

    def test_hay_un_equivalente_dentro_del_menu_movil(self):
        html = self._html()
        menu = html[html.index('id="mobile-menu"'):]
        menu = menu[:menu.index('</nav>')]

        self.assertIn('data-vendedor-toggle', menu)
        self.assertIn('Quantum Coach', menu)
        self.assertIn('coach-orb', menu)

    def test_el_panel_es_un_dialogo_con_nombre_y_region_viva(self):
        html = self._html()
        panel = next(a for e, a in _nodos(html) if a.get('id') == 'vendedor-panel')
        titulo = next(a for e, a in _nodos(html) if a.get('id') == 'vendedor-titulo')
        registro = next(a for e, a in _con_atributo(html, 'data-vendedor-log'))

        self.assertEqual(panel['role'], 'dialog')
        self.assertEqual(panel['aria-modal'], 'true')
        self.assertEqual(panel['aria-labelledby'], 'vendedor-titulo')
        self.assertIn('hidden', panel)
        self.assertIsNotNone(titulo)
        self.assertEqual(registro['aria-live'], 'polite')
        self.assertEqual(registro['role'], 'log')

    def test_la_configuracion_viaja_como_json_y_no_como_script_en_linea(self):
        html = self._html()
        coincidencia = re.search(r'<script id="vendedor-config" type="application/json">(.*?)</script>', html, re.S)

        configuracion = json.loads(coincidencia.group(1))

        self.assertEqual(configuracion['endpoint'], reverse('vendedor:mensaje'))
        self.assertEqual(configuracion['maxLength'], 600)
        self.assertIs(configuracion['disponible'], True)
        self.assertEqual(configuracion['cartUrl'], reverse('carrito:cart_detail'))
        self.assertTrue(configuracion['csrf'])
        # Ningun script ejecutable en linea dentro del panel.
        panel = html[html.index('id="vendedor-panel"'):html.index('</aside>')]
        for etiqueta, atributos in _nodos(panel):
            if etiqueta == 'script':
                self.assertEqual(atributos.get('type'), 'application/json')

    def test_el_encabezado_lleva_la_marca_del_coach(self):
        html = self._html()
        encabezado = html[html.index('class="gtg-vendedor__head"'):]
        encabezado = encabezado[:encabezado.index('</header>')]
        titulo = next(a for e, a in _nodos(encabezado) if a.get('id') == 'vendedor-titulo')

        self.assertIsNotNone(titulo)
        self.assertIn('logo-gotogym-symbol-transparent.png', encabezado)
        self.assertIn('Quantum Coach', encabezado)
        self.assertIn('gtg-vendedor__brand', encabezado)

    def test_hay_sugerencias_para_empezar_y_la_bienvenida_se_presenta(self):
        html = self._html()
        bienvenida = html[html.index('data-vendedor-bienvenida'):]
        sugerencias_bienvenida = bienvenida[:bienvenida.index('</div>', bienvenida.index('data-vendedor-sugerencias'))]
        bienvenida = bienvenida[:bienvenida.index('data-vendedor-sugerencias')]

        self.assertEqual(len(list(_con_atributo(sugerencias_bienvenida, 'data-sugerencia'))), 3)
        self.assertIn('Estoy contigo.', bienvenida)
        self.assertIn('gtg-vendedor__orbit', bienvenida)

    def test_las_mismas_sugerencias_quedan_en_una_fila_para_quien_vuelve(self):
        html = self._html()
        atajos = html[html.index('data-vendedor-atajos'):]
        atajos = atajos[:atajos.index('</div>')]
        textos = [t.strip() for t in re.findall(r'data-sugerencia>([^<]+)<', atajos)]

        self.assertIn('hidden', atajos[:atajos.index('>')], 'oculta hasta que el panel decide mostrarla')
        self.assertEqual(textos, ['Quiero algo para entrenar', '¿Qué talla me conviene?', '¿Cómo funcionan los envíos?'])

    def test_la_configuracion_lleva_la_vigencia_y_las_soluciones(self):
        html = self._html()
        bloque = html[html.index('id="vendedor-config"'):]
        configuracion = json.loads(bloque[bloque.index('>') + 1:bloque.index('</script>')])

        self.assertEqual(configuracion['vigenciaHistorial'], 30 * 60)
        self.assertTrue(all(url.startswith('https://') for url in configuracion['soluciones']))

    def test_saluda_por_nombre_al_usuario_autenticado(self):
        from django.contrib.auth import get_user_model

        usuario = get_user_model().objects.create_user(
            username='juan', email='juan@example.com', first_name='Juan Manuel', password='test-password',
        )
        self.client.force_login(usuario)

        self.assertContains(self.client.get('/es/'), 'Estoy contigo, Juan Manuel.')

    def test_el_estado_de_pensando_lleva_el_orbe_acelerado(self):
        html = self._html()
        estado = html[html.index('data-vendedor-status'):]
        estado = estado[:estado.index('</p>')]

        self.assertIn('coach-orb--busy', estado)
        self.assertIn('Quantum Coach está pensando', estado)

    def test_el_aviso_de_ia_menciona_la_politica_de_datos(self):
        html = self._html()
        aviso = html[html.index('data-vendedor-notice'):]
        aviso = aviso[:aviso.index('data-vendedor-notice-ok')]

        self.assertIn('Soy una IA y puedo equivocarme', aviso)
        self.assertIn(reverse('politica_tratamiento_datos'), aviso)

    def test_los_recursos_llevan_version_para_romper_la_cache(self):
        html = self._html()

        self.assertRegex(html, r'css/vendedor\.css\?v=\S+')
        self.assertRegex(html, r'js/vendedor\.js\?v=\S+')
        self.assertRegex(html, r'js/analytics\.js\?v=20261031-vendedor')

    def test_el_script_se_carga_diferido(self):
        html = self._html()
        etiqueta = re.search(r'<script src="[^"]*vendedor\.js[^"]*"[^>]*>', html).group(0)

        self.assertIn('defer', etiqueta)

    def test_aparece_en_la_tienda_y_en_el_carrito(self):
        for url in (reverse('tienda:producto_list'), reverse('carrito:cart_detail')):
            with self.subTest(url=url):
                self.assertIn('data-vendedor-toggle', self._html(url))

    def test_el_panel_va_fuera_de_la_barra_y_antes_del_contenido(self):
        html = self._html()

        self.assertGreater(html.index('id="vendedor-panel"'), html.index('</nav>'))
        self.assertLess(html.index('id="vendedor-panel"'), html.index('id="main-content"'))

    def test_el_textarea_tiene_etiqueta_y_tope_de_largo(self):
        html = self._html()
        campo = next(a for e, a in _nodos(html) if e == 'textarea' and a.get('id') == 'vendedor-mensaje')

        self.assertEqual(campo['maxlength'], '600')
        self.assertRegex(html, r'<label[^>]*for="vendedor-mensaje"')

    def test_en_el_panel_no_hay_colores_hexadecimales(self):
        # La gobernanza de diseno del CI cuenta los hex de las plantillas.
        self.assertNotRegex(PLANTILLA.read_text(encoding='utf-8'), r'#[0-9A-Fa-f]{3,6}')


@override_settings(
    VENDEDOR_ENABLED=True, VENDEDOR_ROLLOUT_PERCENT=100, COACH_API_URL='', VENDEDOR_COACH_SIMULADO=False,
)
class SinIATests(TestCase):
    """Sin servicio de IA el Coach se muestra y avisa que no esta disponible."""

    def _html(self, idioma='es'):
        return self.client.get(f'/{idioma}/').content.decode()

    def test_el_boton_y_el_panel_siguen_estando(self):
        html = self._html()

        self.assertIn('data-vendedor-toggle', html)
        self.assertIn('id="vendedor-panel"', html)
        self.assertIn('vendedor.js', html)

    def test_la_configuracion_dice_que_no_hay_ia(self):
        html = self._html()
        configuracion = json.loads(re.search(r'id="vendedor-config" type="application/json">(.*?)</script>', html, re.S).group(1))

        self.assertIs(configuracion['disponible'], False)
        self.assertEqual(configuracion['endpoint'], '/es/vendedor/mensaje/')

    def test_la_bienvenida_es_el_aviso_con_el_camino_a_una_persona(self):
        html = self._html()
        bienvenida = html[html.index('data-vendedor-bienvenida'):]
        bienvenida = bienvenida[:bienvenida.index('data-vendedor-status')]

        self.assertIn('En este momento la IA de GoToGym no está disponible. Vuelve más tarde.', bienvenida)
        self.assertIn('href="/es/contacto/"', bienvenida)
        self.assertNotIn('gtg-vendedor__greeting', bienvenida)

    def test_no_hay_sugerencias_ni_aviso_de_ia(self):
        html = self._html()

        self.assertNotIn('data-sugerencia', html)
        self.assertNotIn('data-vendedor-sugerencias', html)
        self.assertNotIn('data-vendedor-notice', html)

    def test_en_ingles_el_aviso_esta_traducido(self):
        html = self._html('en')

        self.assertIn("GoToGym's AI isn't available right now. Please come back later.", html)
        panel = html[html.index('class="gtg-vendedor__scrim"'):html.index('</aside>')]
        self.assertIsNone(re.search(r'[áéíóúñ¿¡]', ' '.join(re.findall(r'>([^<]+)<', panel))))


class SinVendedorTests(TestCase):
    @override_settings(VENDEDOR_ENABLED=False)
    def test_apagado_el_sitio_no_cambia(self):
        html = self.client.get('/es/').content.decode()

        for rastro in ('data-vendedor', 'vendedor-panel', 'vendedor.css', 'vendedor.js', 'gtg-vendedor'):
            self.assertNotIn(rastro, html)

    @override_settings(VENDEDOR_ENABLED=True, VENDEDOR_ROLLOUT_PERCENT=0)
    def test_fuera_del_grupo_expuesto_el_sitio_no_cambia(self):
        html = self.client.get('/es/').content.decode()

        self.assertNotIn('data-vendedor', html)
        self.assertNotIn('vendedor.js', html)


class ReglasDelJavaScriptTests(SimpleTestCase):
    """Reglas de seguridad que no deben volver atras en vendedor.js."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.codigo = _sin_comentarios(JS.read_text(encoding='utf-8'))

    def test_nunca_inserta_html(self):
        for peligroso in ('innerHTML', 'outerHTML', 'insertAdjacentHTML', 'document.write', 'eval(', 'new Function'):
            with self.subTest(peligroso=peligroso):
                self.assertFalse(peligroso in self.codigo, f'vendedor.js usa {peligroso}')

    def test_solo_habla_con_la_propia_tienda(self):
        # Las unicas URLs que usa vienen de la configuracion del panel o de
        # la respuesta ya saneada, y se comprueban contra rutas internas.
        self.assertIsNone(re.search(r'https?://', self.codigo))

    def test_valida_las_rutas_antes_de_usarlas(self):
        for nombre in ('RUTA_ENLACE', 'RUTA_IMAGEN', 'RUTA_AGREGAR'):
            self.assertIn(nombre, self.codigo)

    def test_no_lleva_cadenas_visibles_en_espanol(self):
        # Los textos viven en el panel, traducidos. Una cadena con acentos o
        # signos de apertura delataria texto escrito a mano en el script.
        cadenas = re.findall(r"'([^'\n]*)'|\"([^\"\n]*)\"", self.codigo)
        for simple, doble in cadenas:
            with self.subTest(cadena=simple or doble):
                self.assertNotRegex(simple or doble, r'[áéíóúñ¿¡ÁÉÍÓÚÑ]')

    def test_la_sintaxis_es_valida(self):
        node = shutil.which('node')
        if node is None:
            self.skipTest('Node no esta disponible')
        resultado = subprocess.run([node, '--check', str(JS)], capture_output=True, text=True, timeout=60)

        self.assertEqual(resultado.returncode, 0, resultado.stderr)

    def test_los_eventos_que_mide_estan_declarados_en_el_servidor(self):
        from analitica.views import EVENTOS_PERMITIDOS

        medidos = set(re.findall(r"medir\('(vendedor_[a-z_]+)'", self.codigo))
        medidos.add('vendedor_open')  # lo emite el atributo data-track del boton

        self.assertEqual(medidos, {e for e in EVENTOS_PERMITIDOS if e.startswith('vendedor_')})

    def test_no_envia_texto_de_mensajes_a_la_medicion(self):
        for llamada in re.findall(r"medir\([^;]*\);", self.codigo):
            with self.subTest(llamada=llamada[:60]):
                self.assertNotRegex(llamada, r'mensaje|reply|\.t\b|campo\.value|texto\(')


class ReglasDelCSSTests(SimpleTestCase):
    def test_no_define_colores_nuevos(self):
        css = CSS.read_text(encoding='utf-8')
        sin_comentarios = re.sub(r'/\*.*?\*/', '', css, flags=re.S)

        self.assertNotRegex(sin_comentarios, r'#[0-9A-Fa-f]{3,8}\b')
        self.assertNotRegex(sin_comentarios, r'\b(rgb|rgba|hsl|hsla)\(')

    def test_el_panel_queda_por_encima_de_la_barra_y_del_minicarrito(self):
        css = CSS.read_text(encoding='utf-8')
        z_panel = int(re.search(r'\.gtg-vendedor \{[^}]*z-index:\s*(\d+)', css).group(1))

        self.assertGreater(z_panel, 70)  # .gtg-minicart usa 70; la barra 50 y el menu movil 60

    def test_el_panel_de_escritorio_mide_un_tercio_de_la_pantalla(self):
        css = CSS.read_text(encoding='utf-8')

        self.assertRegex(css, r':root \{[^}]*--coach-ancho:\s*clamp\(\s*\d+px,\s*33\.333vw,\s*\d+px\s*\)')
        self.assertRegex(css, r'\.gtg-vendedor \{[^}]*width:\s*var\(--coach-ancho\)')

    def test_el_banner_de_cookies_se_acomoda_con_la_misma_medida_del_panel(self):
        css = CSS.read_text(encoding='utf-8')

        # Una sola fuente de verdad: si el ancho del panel cambia, el banner lo sigue.
        self.assertIn('calc(100vw - var(--coach-ancho)', css)
        self.assertNotIn('420px', css)

    def test_en_movil_la_barra_muestra_el_orbe_y_la_etiqueta_ia(self):
        css = CSS.read_text(encoding='utf-8')
        inicio = css.rindex('@media (max-width: 900px) {')
        movil = css[inicio:]

        # El boton no se oculta: orbe y etiqueta "IA", tactil de 44 px.
        self.assertRegex(movil, r'\.gtg-vendedor-toggle \{[^}]*min-width: 44px;[^}]*height: 44px;')
        self.assertNotRegex(movil, r'\.gtg-vendedor-toggle \{[^}]*display:\s*none')
        self.assertRegex(movil, r'\.gtg-vendedor-toggle \.gtg-vendedor-toggle__label \{[^}]*display: none')
        self.assertRegex(movil, r'\.gtg-vendedor-toggle \.gtg-vendedor-toggle__badge \{[^}]*display: inline-block')
        # La regla de movil no esconde la etiqueta de la entrada del menu.
        self.assertNotRegex(movil, r'(^|\n)\s*\.gtg-vendedor-toggle__badge[^{]*\{[^}]*display: none')
        # El panel ocupa toda la pantalla.
        self.assertRegex(movil, r'\.gtg-vendedor \{[^}]*width: 100vw')

    def test_el_orbe_es_css_puro_y_se_detiene_con_menos_movimiento(self):
        css = CSS.read_text(encoding='utf-8')

        for pieza in ('.coach-orb {', '.coach-orb::before', '.coach-orb::after', '@keyframes coach-orbita',
                      '@keyframes coach-respira'):
            with self.subTest(pieza=pieza):
                self.assertIn(pieza, css)
        # La regla global de style.css para prefers-reduced-motion anula las
        # animaciones con `animation-duration`: esta hoja no debe fijarlas con !important.
        self.assertNotIn('!important', css.replace('display: none !important;', ''))

    def test_las_mezclas_translucidas_tienen_valor_de_respaldo(self):
        css = CSS.read_text(encoding='utf-8')

        self.assertIn('@supports (background: color-mix(in srgb, red, blue))', css)
        self.assertRegex(css, r'\.gtg-vendedor \{[^}]*border-left: 1px solid var\(--color-border\)')

    def test_el_boton_de_la_barra_va_sin_contorno_de_pastilla(self):
        css = CSS.read_text(encoding='utf-8')

        self.assertRegex(css, r'\.gtg-vendedor-toggle \{[^}]*border: 0;[^}]*background: transparent;')
        self.assertRegex(css, r'\.gtg-vendedor-toggle \{[^}]*color: var\(--color-premium-white\)')

    def test_la_etiqueta_ia_usa_el_dorado_de_la_marca(self):
        css = CSS.read_text(encoding='utf-8')

        self.assertRegex(css, r'\.gtg-vendedor-toggle__badge \{[^}]*background: var\(--color-gold\)')

    def test_los_controles_tienen_tamano_tactil_minimo(self):
        css = CSS.read_text(encoding='utf-8')

        self.assertRegex(css, r'\.gtg-vendedor-toggle \{[^}]*min-height:\s*44px')
        self.assertRegex(css, r'\.gtg-vendedor__button \{[^}]*min-height:\s*44px')
        self.assertRegex(css, r'\.gtg-vendedor__icon-button \{[^}]*height:\s*44px')
