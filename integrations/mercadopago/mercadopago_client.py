import os

try:
    import mercadopago
except ImportError:  # pragma: no cover - mercadopago may not be installed
    mercadopago = None


class MercadoPagoClient:
    """Lightweight Mercado Pago wrapper."""

    def __init__(self, access_token: str | None = None) -> None:
        self.access_token = access_token or os.environ.get("MERCADOPAGO_ACCESS_TOKEN")
        if mercadopago is None:
            raise RuntimeError("mercadopago package is required")
        self.sdk = mercadopago.SDK(self.access_token)

    def create_preference(self, preference_data: dict) -> dict:
        """Create a payment preference and return the API response."""
        result = self.sdk.preference().create(preference_data)
        return result.get("response", {})
