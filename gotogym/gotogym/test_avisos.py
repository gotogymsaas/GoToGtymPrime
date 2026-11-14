"""Avisos del sitio (partials/_mensajes.html): un solo lugar, discreto y sin acumularse."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from vendedor.test_utilidades import aislar_catalogo, crear_producto

DESACTIVADA = "Desactivamos la personalización con Quantum Coach."


class AvisosTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="eva@example.com", username="eva", password="x")
        self.client.force_login(self.user)

    def apagar_personalizacion(self, **kwargs):
        return self.client.post(reverse("vendedor:personalizacion_todo"), {"accion": "desactivar"}, **kwargs)

    def test_el_aviso_sale_en_la_pagina_de_la_accion(self):
        html = self.apagar_personalizacion(follow=True).content.decode()
        self.assertIn('class="gtg-aviso gtg-aviso--success"', html)
        self.assertEqual(html.count(DESACTIVADA), 1)
        # Una confirmacion se cierra sola y no se anuncia como alerta.
        self.assertIn("data-aviso-temporal", html)
        self.assertIn('role="status"', html)

    def test_no_se_acumulan_en_la_siguiente_pagina(self):
        self.apagar_personalizacion(follow=True)
        self.assertNotIn("gtg-aviso", self.client.get(reverse("edit_profile")).content.decode())

    def test_un_error_espera_a_que_lo_cierren(self):
        # Activar sin cuenta vinculada es un error.
        html = self.client.post(
            reverse("vendedor:personalizacion_todo"), {"accion": "activar"}, follow=True,
        ).content.decode()
        self.assertIn('class="gtg-aviso gtg-aviso--error"', html)
        self.assertIn('role="alert"', html)
        self.assertNotIn("data-aviso-temporal", html)

    def test_los_errores_del_perfil_ahora_se_ven(self):
        html = self.client.post(reverse("edit_profile"), {
            "first_name": "Eva", "email": "eva@example.com", "age": "no-es-numero",
        }, follow=True).content.decode()
        self.assertIn("gtg-aviso--error", html)

    def test_la_ficha_de_producto_pinta_el_aviso_una_vez_y_sin_bloque_rojo(self):
        aislar_catalogo()
        producto, _ = crear_producto("Chaqueta Quantum", [("M", "gris", 3, {})])
        self.apagar_personalizacion()  # sin seguir la redireccion: el aviso queda pendiente
        html = self.client.get(reverse("tienda:producto_detail", args=[producto.pk])).content.decode()
        self.assertEqual(html.count(DESACTIVADA), 1)
        self.assertNotIn("bg-red-50", html)


class AvisosEnFormulariosTests(TestCase):
    def test_el_registro_no_repite_el_error_del_formulario(self):
        html = self.client.post(reverse("register"), {}).content.decode()
        self.assertEqual(html.count("Completa tu nombre, correo y contraseña, y acepta los términos."), 1)
        self.assertNotIn("gtg-aviso--error", html)
