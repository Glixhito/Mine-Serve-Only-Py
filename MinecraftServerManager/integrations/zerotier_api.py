"""Cliente de la API de ZeroTier Central: crea una red por servidor y autoriza miembros."""
from __future__ import annotations

from integrations import http_client

BASE_URL = "https://api.zerotier.com/api/v1"
POOL = ("10.147.20.1", "10.147.20.254")  # rango de IP que ZeroTier asigna a los miembros
SUBNET = "10.147.20.0/24"


class ZeroTierError(RuntimeError):
    """Fallo al hablar con ZeroTier. El mensaje está pensado para el usuario."""


class ZeroTierCentral:
    def __init__(self, token: str) -> None:
        self._headers = {"Authorization": f"bearer {token}"}

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        response = http_client.client().request(method, f"{BASE_URL}{path}", headers=self._headers, json=body)
        if response.status_code == 401:
            raise ZeroTierError("El token de ZeroTier no es válido. Revísalo en la pestaña ZeroTier.")
        if response.status_code >= 400:
            raise ZeroTierError(f"ZeroTier respondió {response.status_code}: {response.text[:200]}")
        return response.json() if response.content else {}

    def create_network(self, name: str) -> str:
        body = {"config": {
            "name": name,
            "private": True,
            "v4AssignMode": {"zt": True},
            "ipAssignmentPools": [{"ipRangeStart": POOL[0], "ipRangeEnd": POOL[1]}],
            "routes": [{"target": SUBNET, "via": None}],
        }}
        return self._request("POST", "/network", body)["id"]

    def authorize_member(self, network_id: str, node_id: str) -> None:
        self._request("POST", f"/network/{network_id}/member/{node_id}", {"config": {"authorized": True}})