"""Agente 3: precios con descuento y solo los cupones de campana marcados, nunca los de afiliados."""
from datetime import timedelta
from decimal import Decimal

from accounts.models import CustomerSegment
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from orders.models import Coupon

from . import contrato, evidencia
from .test_utilidades import crear_producto


class PromocionesTests(TestCase):
    def setUp(self):
        # Una migracion siembra el cupon heredado CUPON; cada prueba parte de cero.
        Coupon.objects.all().delete()

    def cupon(self, code, **campos):
        campos.setdefault("coach_can_offer", True)
        return Coupon.objects.create(code=code, discount_type=campos.pop("discount_type", "percentage"),
                                     value=campos.pop("value", Decimal("10")), **campos)

    def afiliado(self, codigo):
        from afiliados.models import PerfilAfiliado

        user = get_user_model().objects.create_user(username=codigo.lower(), email=f"{codigo.lower()}@example.com",
                                                    password="x-test")
        return PerfilAfiliado.objects.create(user=user, referral_code=codigo, status="approved")

    def test_solo_cupones_marcados_vigentes_y_sin_segmento(self):
        ahora = timezone.now()
        self.cupon("BIENVENIDA", min_purchase=Decimal("100000"), ends_at=ahora + timedelta(days=5))
        self.cupon("APAGADO", is_active=False)
        self.cupon("VENCIDO", ends_at=ahora - timedelta(days=1))
        self.cupon("FUTURO", starts_at=ahora + timedelta(days=1))
        self.cupon("AGOTADO", max_uses=1, times_used=1)
        self.cupon("SEGMENTO", customer_segment=CustomerSegment.objects.create(name="Mayorista"))
        self.cupon("SINMARCAR", coach_can_offer=False)
        filas = evidencia.promociones()
        self.assertEqual([f["code"] for f in filas], ["BIENVENIDA"])
        self.assertEqual(filas[0]["min_purchase"], "100000.00")
        self.assertEqual(filas[0]["ends_on"], timezone.localdate(ahora + timedelta(days=5)).isoformat())

    def test_un_cupon_sin_marcar_no_viaja_aunque_sea_de_libre_acceso(self):
        # Por defecto ningun cupon se ofrece: el administrador lo habilita a mano.
        Coupon.objects.create(code="CUPON", value=Decimal("10"))
        self.assertEqual(evidencia.promociones(), [])

    def test_cupon_de_afiliado_nunca_viaja_aunque_este_marcado(self):
        self.cupon("AFILIADO10", afiliado=self.afiliado("AFILIADO10"))
        self.assertEqual(evidencia.promociones(), [])

    def test_codigo_de_afiliado_sin_vinculo_tampoco_viaja(self):
        # El vinculo `afiliado` puede faltar (cupon creado a mano) o perderse
        # (SET_NULL); el codigo sigue siendo del afiliado.
        self.afiliado("MiMarca3")
        self.cupon("MIMARCA3")
        self.assertEqual(evidencia.promociones(), [])

    def test_codigo_fuera_de_formato_se_omite_sin_romper(self):
        self.cupon("con espacio")
        self.assertEqual(evidencia.promociones(), [])

    def test_variante_con_descuento_lleva_precio_de_lista(self):
        _, (con, sin) = crear_producto("Legging", [
            ("M", "Negro", 3, {"discount_price": Decimal("80000")}), ("L", "Negro", 3)])
        con_datos, sin_datos = evidencia._variante(con), evidencia._variante(sin)
        self.assertEqual((con_datos["price"], con_datos["list_price"]), ("80000.00", "100000.00"))
        self.assertNotIn("list_price", sin_datos)

    def test_el_contrato_valida_las_promociones(self):
        base = {"code": "BIENVENIDA", "discount_type": "percentage", "value": "10.00",
                "min_purchase": None, "ends_on": None}
        for malo in ({**base, "code": "minusculas"}, {**base, "discount_type": "gratis"},
                     {**base, "afiliado": "x"}, {**base, "value": "diez"}):
            with self.subTest(malo):
                with self.assertRaises(contrato.ContratoInvalido):
                    contrato.validar_solicitud(_solicitud_con([malo]))
        contrato.validar_solicitud(_solicitud_con([base]))


def _solicitud_con(promociones):
    return {
        "request_id": "req-0001", "conversation_id": "shop-12345678", "locale": "es", "message": "hola",
        "timestamp": 1, "visitor": {"subject": "shop_v_abc12345", "authenticated": False},
        "page": {"url_name": "", "product_id": None, "variant_id": None, "filtro": ""},
        "cart": {"count": 0, "subtotal": "0.00", "lines": []},
        "shop_flags": {"purchases_paused": False, "payments_live": False, "currency": "COP"},
        "evidence": {"candidates": [], "policies": [], "promotions": promociones,
                     "claims_policy": {"version": "v1", "prohibited": []}},
    }
