"""Versiones oficiales de Minecraft: índice en memoria y descarga del server.jar."""
from __future__ import annotations

from pathlib import Path

from integrations import http_client, minecraft_api


class VersionManager:
    def __init__(self, cache_dir: Path) -> None:
        self._cache = cache_dir
        self._index: dict[str, dict] | None = None
        self._releases: list[str] = []

    def _load(self) -> dict[str, dict]:
        if self._index is None:
            entries = minecraft_api.fetch_manifest(self._cache)["versions"]
            self._index = {entry["id"]: entry for entry in entries}  # búsqueda O(1) por id
            self._releases = [entry["id"] for entry in entries if entry["type"] == "release"]
        return self._index

    def list_release_versions(self) -> list[str]:
        self._load()
        return list(self._releases)

    def download_server_jar(self, version_id: str, target: Path) -> Path:
        index = self._load()
        if version_id not in index:
            raise http_client.DownloadError(f"La versión {version_id} no existe en el manifiesto oficial.")
        info = minecraft_api.get_server_download(index[version_id], self._cache)
        return http_client.download_file(info.url, target, expected_sha1=info.sha1)
