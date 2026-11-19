"""API oficial de Mojang: manifiesto de versiones y datos de descarga del servidor."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from integrations import http_client

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"


@dataclass(frozen=True)
class ServerDownload:
    url: str
    sha1: str
    size: int


def fetch_manifest(cache_dir: Path | None = None) -> dict:
    return http_client.get_json(MANIFEST_URL, cache_dir)


def get_server_download(version_entry: dict, cache_dir: Path | None = None) -> ServerDownload:
    """La ficha de cada versión no cambia: con caché ETag no se vuelve a descargar."""
    data = http_client.get_json(version_entry["url"], cache_dir)
    server = data.get("downloads", {}).get("server")
    if not server:
        raise http_client.DownloadError(f"La versión {version_entry['id']} no publica un servidor.")
    return ServerDownload(url=server["url"], sha1=server["sha1"], size=server["size"])
