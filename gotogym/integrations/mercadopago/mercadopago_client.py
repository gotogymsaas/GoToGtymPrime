import os

try:
    import mercadopago
except ImportError:  # pragma: no cover - mercadopago may not be installed
    mercadopago = None


class MercadoPagoError(Exception):
    """Mercado Pago respondio con un error (o no respondio lo esperado)."""


def _respuesta_valida(resultado: dict, accion: str) -> dict:
    """El SDK no lanza ante un 4xx/5xx: devuelve `{"status": ..., "response": ...}`.

    Sin esta comprobacion, un token invalido o una preferencia rechazada
    parecian un exito con respuesta vacia, y se guardaba una transaccion sin
    `preference_id` que nunca podia pagarse.
    """
    estado = resultado.get("status")
    if estado is None or not 200 <= int(estado) < 300:
        detalle = resultado.get("response") or {}
        mensaje = detalle.get("message") if isinstance(detalle, dict) else detalle
        raise MercadoPagoError(f"{accion}: HTTP {estado} {mensaje or ''}".strip())
    return resultado.get("response", {})


class MercadoPagoClient:
    """Lightweight Mercado Pago wrapper."""

    def __init__(self, access_token: str | None = None) -> None:
        self.access_token = access_token or os.environ.get("MERCADOPAGO_ACCESS_TOKEN")
        if mercadopago is None:
            raise RuntimeError("mercadopago package is required")
        if not self.access_token:
            raise RuntimeError("MERCADOPAGO_ACCESS_TOKEN no esta configurado")
        self.sdk = mercadopago.SDK(self.access_token)

    def create_preference(self, preference_data: dict) -> dict:
        """Create a payment preference and return the API response."""
        result = self.sdk.preference().create(preference_data)
        return _respuesta_valida(result, "No se pudo crear la preferencia de pago")

    def get_payment(self, payment_id: str) -> dict:
        """Consulta un pago por su id. Es la fuente de verdad del estado: lo
        que llega en un webhook o en la URL de retorno solo avisa que hay algo
        que consultar, no se toma como cierto."""
        result = self.sdk.payment().get(payment_id)
        return _respuesta_valida(result, f"No se pudo consultar el pago {payment_id}")

    def refund_payment(self, payment_id: str, amount: float | None = None) -> dict:
        """Refund a payment, fully or partially, and return the API response."""
        refund_object = {"amount": amount} if amount is not None else None
        result = self.sdk.refund().create(payment_id, refund_object)
        return _respuesta_valida(result, f"No se pudo reembolsar el pago {payment_id}")
