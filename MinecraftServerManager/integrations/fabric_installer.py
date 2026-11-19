"""Instalador de Fabric: valida la versión del cargador antes de descargar y luego obtiene el servidor."""
from __future__ import annotations

import zipfile
from pathlib import Path

from integrations import http_client
from integrations.loader_base import LoaderError

META = "https://meta.fabricmc.net/v2/versions"


class FabricInstaller:
    loader = "fabric"
    needs_java = False  # descargar no ejecuta Java; el servidor sí

    def __init__(self, cache_dir: Path) -> None:
        self._cache = cache_dir

    def _entries(self, minecraft_version: str) -> list[dict]:
        """Versiones del cargador para una versión de Minecraft, de la más nueva a la más antigua."""
        items = http_client.get_json(f"{META}/loader/{minecraft_version}", self._cache)
        return [{"version": item["loader"]["version"], "stable": bool(item["loader"].get("stable"))}
                for item in items]

    def loader_versions(self, minecraft_version: str) -> list[str]:
        return [entry["version"] for entry in self._entries(minecraft_version)]

    def recommended_version(self, minecraft_version: str) -> str | None:
        """La versión estable más reciente para esa versión de Minecraft."""
        for entry in self._entries(minecraft_version):
            if entry["stable"]:
                return entry["version"]
        return None

    def latest_installer(self) -> str:
        items = http_client.get_json(f"{META}/installer", self._cache)
        return next(item["version"] for item in items if item.get("stable"))

    def install(self, server_dir: Path, minecraft_version: str, loader_version: str, java_path: str = "") -> dict:
        entries = self._entries(minecraft_version)
        if not entries:
            raise LoaderError(f"Fabric no tiene cargador para Minecraft {minecraft_version}.")
        if loader_version not in {entry["version"] for entry in entries}:
            recommended = self.recommended_version(minecraft_version)
            hint = f" Usa la versión recomendada: {recommended}." if recommended else ""
            raise LoaderError(f"«{loader_version}» no es una versión de Fabric para Minecraft "
                              f"{minecraft_version}.{hint}")
        url = f"{META}/loader/{minecraft_version}/{loader_version}/{self.latest_installer()}/server/jar"
        target = server_dir / "server.jar"
        http_client.download_file(url, target)
        if not zipfile.is_zipfile(target):  # Fabric no publica hash aquí: al menos se valida el formato
            target.unlink(missing_ok=True)
            raise LoaderError("Fabric no devolvió un JAR válido.")
        return {"mode": "jar", "target": "server.jar"}