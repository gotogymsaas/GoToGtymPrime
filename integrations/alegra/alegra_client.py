import base64
import os
from typing import Any

import requests


class AlegraClient:
    """Simple client for interacting with Alegra API."""

    BASE_URL = "https://api.alegra.com/api/v1/"

    def __init__(self, email: str | None = None, token: str | None = None) -> None:
        self.email = email or os.environ.get("ALEGRA_EMAIL")
        self.token = token or os.environ.get("ALEGRA_TOKEN")
        if not self.email or not self.token:
            raise ValueError("Alegra credentials are required")
        credentials = f"{self.email}:{self.token}"
        auth = base64.b64encode(credentials.encode()).decode()
        self.headers = {"Authorization": f"Basic {auth}"}

    def create_invoice(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create an invoice using Alegra API."""
        url = self.BASE_URL + "invoices"
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()

    def record_expense(self, data: dict[str, Any]) -> dict[str, Any]:
        """Record an expense using Alegra API."""
        url = self.BASE_URL + "expenses"
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()
