import os

class HubSpotClient:
    """Simple client for creating contacts in HubSpot."""

    def __init__(self, token: str | None = None) -> None:
        self.token = token or os.environ.get("HUBSPOT_PRIVATE_TOKEN")

    def create_contact(self, email: str, data: dict | None = None) -> None:
        """Send contact data to HubSpot (stubbed)."""
        # Real implementation would make an HTTP request here
        pass
