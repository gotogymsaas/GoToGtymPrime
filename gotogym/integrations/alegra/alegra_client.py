import base64
import os
import re
from typing import Any

import requests

# Segundos que se espera a Alegra por llamada. Emitir ante la DIAN es lo mas
# lento; sin tope, un Alegra caido dejaria colgada la peticion que lo origino.
TIMEOUT = 15


class AlegraConfigError(ValueError):
    """Faltan las credenciales de Alegra."""


class AlegraError(Exception):
    """Alegra respondio con un error o no se pudo hablar con ella.

    `status` es el codigo HTTP (None si no hubo respuesta) y `payload` el
    cuerpo JSON del error cuando lo hay. El mensaje no incluye la URL ni las
    cabeceras, para poder guardarlo o mostrarlo sin filtrar credenciales.
    """

    def __init__(self, message: str, status: int | None = None, payload: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.payload = payload


def _solo_alfanumerico(valor: Any) -> str:
    return re.sub(r'[^0-9A-Za-z]', '', str(valor or ''))


def _mensaje_de_error(payload: Any, status: int | None) -> str:
    if isinstance(payload, dict):
        error = payload.get('error', payload.get('message'))
        if isinstance(error, dict):
            error = error.get('message')
        if error:
            return f'Alegra respondió {status}: {error}'
    return f'Alegra respondió {status}'


class AlegraClient:
    """Simple client for interacting with Alegra API."""

    BASE_URL = "https://api.alegra.com/api/v1/"

    def __init__(self, email: str | None = None, token: str | None = None) -> None:
        self.email = email or os.environ.get("ALEGRA_EMAIL")
        self.token = token or os.environ.get("ALEGRA_API_TOKEN") or os.environ.get("ALEGRA_TOKEN")
        if not self.email or not self.token:
            raise AlegraConfigError("Alegra credentials are required")
        credentials = f"{self.email}:{self.token}"
        auth = base64.b64encode(credentials.encode()).decode()
        self.headers = {"Authorization": f"Basic {auth}"}

    @classmethod
    def from_settings(cls) -> "AlegraClient":
        """Cliente con las credenciales de `settings` (donde las lee el sitio)."""
        from django.conf import settings

        return cls(
            email=getattr(settings, "ALEGRA_EMAIL", None),
            token=getattr(settings, "ALEGRA_API_TOKEN", None),
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = self.BASE_URL + path
        try:
            response = getattr(requests, method)(
                url, headers=self.headers, timeout=TIMEOUT, **kwargs,
            )
            response.raise_for_status()
        except requests.HTTPError as error:
            respuesta = error.response
            status = getattr(respuesta, "status_code", None)
            try:
                payload = respuesta.json()
            except (AttributeError, ValueError):
                payload = None
            raise AlegraError(_mensaje_de_error(payload, status), status, payload) from error
        except requests.RequestException as error:
            raise AlegraError(f"No se pudo conectar con Alegra ({type(error).__name__})") from error
        return response.json()

    def create_invoice(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create an invoice using Alegra API."""
        return self._request("post", "invoices", json=data)

    def get_invoice(self, invoice_id: str | int) -> dict[str, Any]:
        """Fetch a single invoice."""
        return self._request("get", f"invoices/{invoice_id}")

    def delete_invoice(self, invoice_id: str | int) -> Any:
        """Delete an invoice. Alegra only allows it while it is a draft."""
        return self._request("delete", f"invoices/{invoice_id}")

    def get_clients(self) -> list[dict[str, Any]]:
        """List clients from Alegra."""
        return self._request("get", "contacts")

    def find_contact(self, number: str, dv: str = "") -> dict[str, Any] | None:
        """Busca un cliente por su numero de documento (coincidencia exacta).

        El filtro `identification` de Alegra es de coincidencia parcial, asi
        que se compara aqui el numero completo de cada resultado.
        """
        buscado = _solo_alfanumerico(number)
        candidatos = {buscado, buscado + _solo_alfanumerico(dv)} if dv else {buscado}
        resultados = self._request(
            "get", "contacts", params={"identification": buscado, "type": "client", "limit": 30},
        )
        for contacto in resultados or []:
            numero = _solo_alfanumerico((contacto.get("identificationObject") or {}).get("number"))
            completo = _solo_alfanumerico(contacto.get("identification"))
            if numero in candidatos or completo in candidatos:
                return contacto
        return None

    def create_contact(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a client in Alegra."""
        return self._request("post", "contacts", json=data)

    def find_item(self, reference: str) -> dict[str, Any] | None:
        """Busca un producto por su referencia (coincidencia exacta)."""
        resultados = self._request("get", "items", params={"query": reference, "limit": 30})
        for item in resultados or []:
            if item.get("reference") == reference:
                return item
        return None

    def create_item(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a product or service in Alegra."""
        return self._request("post", "items", json=data)

    def get_invoices(self) -> list[dict[str, Any]]:
        """List invoices from Alegra."""
        return self._request("get", "invoices")

    def record_expense(self, data: dict[str, Any]) -> dict[str, Any]:
        """Record an expense using Alegra API."""
        return self._request("post", "expenses", json=data)
