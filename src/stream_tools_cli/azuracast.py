"""AzuraCast API integration for station control."""

import os
from dataclasses import dataclass
from urllib.parse import urljoin

import requests


@dataclass
class AzuraCastConfig:
    """AzuraCast connection configuration."""

    url: str  # e.g., "https://radio.example.com"
    api_key: str
    station_id: str  # e.g., "1" or "delicious_radio"

    @classmethod
    def from_env(cls) -> "AzuraCastConfig | None":
        """Load config from environment variables.

        Expected vars:
            AZURACAST_URL: Base URL of AzuraCast instance
            AZURACAST_API_KEY: API key from AzuraCast
            AZURACAST_STATION_ID: Numeric station ID (e.g., "1")

        Returns:
            Config if all vars are set, None otherwise.
        """
        url = os.environ.get("AZURACAST_URL")
        api_key = os.environ.get("AZURACAST_API_KEY")
        station_id = os.environ.get("AZURACAST_STATION_ID")

        if url and api_key and station_id:
            return cls(url=url.rstrip("/"), api_key=api_key, station_id=station_id)
        return None


class AzuraCastClient:
    """Client for AzuraCast API."""

    def __init__(self, config: AzuraCastConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers["X-API-Key"] = config.api_key

    def _url(self, path: str) -> str:
        """Build full API URL."""
        return urljoin(self.config.url, f"/api/station/{self.config.station_id}/{path}")

    def _post(self, path: str) -> dict:
        """Make POST request to API."""
        response = self.session.post(self._url(path))
        response.raise_for_status()
        return response.json()

    def restart_backend(self) -> dict:
        """Restart liquidsoap backend."""
        return self._post("backend/restart")

    def stop_backend(self) -> dict:
        """Stop liquidsoap backend."""
        return self._post("backend/stop")

    def start_backend(self) -> dict:
        """Start liquidsoap backend."""
        return self._post("backend/start")

    def restart_frontend(self) -> dict:
        """Restart streaming frontend (icecast/shoutcast)."""
        return self._post("frontend/restart")

    def get_status(self) -> dict:
        """Get station info."""
        response = self.session.get(
            urljoin(self.config.url, f"/api/station/{self.config.station_id}")
        )
        response.raise_for_status()
        return response.json()

    def get_service_status(self) -> dict:
        """Get station service status (backend/frontend running state)."""
        response = self.session.get(self._url("status"))
        response.raise_for_status()
        return response.json()

    def get_nowplaying(self) -> dict:
        """Get now playing info including listeners."""
        response = self.session.get(
            urljoin(self.config.url, f"/api/nowplaying/{self.config.station_id}")
        )
        response.raise_for_status()
        return response.json()


def get_azuracast_client() -> AzuraCastClient | None:
    """Get AzuraCast client if configured.

    Returns:
        Client instance if env vars are set, None otherwise.
    """
    config = AzuraCastConfig.from_env()
    if config:
        return AzuraCastClient(config)
    return None
