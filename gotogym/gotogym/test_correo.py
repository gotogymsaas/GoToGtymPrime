"""Correos con diseño: el HTML de marca y su texto salen del mismo contenido."""
from django.core import mail
from django.test import SimpleTestCase, override_settings

from gotogym.correo import (
    Correo,
    aviso,
    boton,
    datos,
    enviar_correo,
    parrafo,
    productos,
    totales,
    url_absoluta,
)


def _correo(**cambios):
    datos_base = dict(
        asunto='Recibimos tu pedido GTG-1', titulo='Recibimos tu pedido', kicker='Pedido GTG-1', saludo='Hola Ana,',
        pie='Recibes este correo porque hiciste un pedido.',
        bloques=[
            parrafo('Recibimos tu pedido y está pendiente de pago.'),
            productos([{'nombre': 'Leggins', 'detalle': 'L / negro', 'cantidad': 2, 'total': '$800.000', 'imagen': ''}]),
            totales([('Subtotal', '$800.000'), ('Total', '$812.000')]),
            datos([('Transportadora', 'GoToGym Envios')]),
            aviso('Si no pagas en 48 horas se cancela.'),
            boton('Ver mi pedido', 'https://gotogym.store/p/1/', texto_plano='Mira tu pedido aquí: https://gotogym.store/p/1/'),
        ],
    )
    datos_base.update(cambios)
    return Correo(**datos_base)


@override_settings(SITIO_URL='https://shop.gotogym.store')
class CorreoDeMarcaTests(SimpleTestCase):
    def test_el_html_trae_la_marca_y_el_contenido(self):
        html = _correo().html()
        self.assertIn('<!DOCTYPE html>', html)
        self.assertIn('#101012', html)  # negro de la marca
        self.assertIn('https://shop.gotogym.store/static/', html)  # el logo lleva direccion absoluta
        self.assertIn('Recibimos tu pedido', html)
        self.assertIn('$812.000', html)
        self.assertIn('Ver mi pedido', html)
        self.assertIn('https://gotogym.store/p/1/', html)

    def test_el_texto_lleva_lo_mismo_en_orden(self):
        texto = _correo().texto()
        esperado = [
            'Hola Ana,', 'Recibimos tu pedido y está pendiente de pago.',
            '- Leggins (L / negro) x2: $800.000', 'Subtotal: $800.000', 'Total: $812.000',
            'Transportadora: GoToGym Envios', 'Si no pagas en 48 horas se cancela.',
            'Mira tu pedido aquí: https://gotogym.store/p/1/', 'Equipo GoToGym', 'support@gotogym.store',
        ]
        posiciones = [texto.index(fragmento) for fragmento in esperado]
        self.assertEqual(posiciones, sorted(posiciones))

    def test_el_boton_sin_frase_propia_usa_texto_y_enlace(self):
        texto = _correo(bloques=[boton('Ir al panel', 'https://gotogym.store/panel/')]).texto()
        self.assertIn('Ir al panel: https://gotogym.store/panel/', texto)

    def test_el_html_escapa_lo_que_viene_de_fuera(self):
        html = _correo(bloques=[
            parrafo('<script>alert(1)</script>'),
            productos([{'nombre': '"><img src=x onerror=1>', 'detalle': 'S', 'cantidad': 1, 'total': '$1', 'imagen': ''}]),
        ]).html()
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertNotIn('"><img src=x', html)
        self.assertIn('&lt;script&gt;', html)

    def test_una_linea_sin_foto_no_deja_una_imagen_rota(self):
        sin_foto = _correo().html()
        con_foto = _correo(bloques=[productos([
            {'nombre': 'Leggins', 'detalle': 'L / negro', 'cantidad': 1, 'total': '$1', 'imagen': 'https://x.test/a.png'},
        ])]).html()
        self.assertNotIn('class="gtg-foto"', sin_foto)
        self.assertIn('<img class="gtg-foto" src="https://x.test/a.png"', con_foto)

    def test_la_previa_sale_del_primer_parrafo_si_no_se_indica(self):
        self.assertIn('Recibimos tu pedido y está pendiente de pago.', _correo().html())
        self.assertIn('Texto de previa', _correo(previa='Texto de previa').html())

    def test_un_bloque_desconocido_falla_en_vez_de_perderse(self):
        with self.assertRaises(ValueError):
            _correo(bloques=[{'tipo': 'inventado'}]).texto()

    def test_se_envia_en_texto_y_html(self):
        enviados = enviar_correo('ana@example.com', _correo())
        self.assertEqual(enviados, 1)
        mensaje = mail.outbox[0]
        self.assertEqual(mensaje.to, ['ana@example.com'])
        self.assertEqual(mensaje.subject, 'Recibimos tu pedido GTG-1')
        self.assertIn('Recibimos tu pedido y está pendiente de pago.', mensaje.body)
        (contenido, tipo), = mensaje.alternatives
        self.assertEqual(tipo, 'text/html')
        self.assertIn('<!DOCTYPE html>', contenido)

    def test_url_absoluta(self):
        self.assertEqual(url_absoluta('/media/a.png'), 'https://shop.gotogym.store/media/a.png')
        self.assertEqual(url_absoluta('https://cdn.test/a.png'), 'https://cdn.test/a.png')
