"""Instalador de Forge (versiones que usan --installServer)."""
from __future__ import annotations

from pathlib import Path

from integrations import http_client
from integrations.loader_base import InstallerLoader

PROMOS_URL = "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"


class ForgeInstaller(InstallerLoader):
    loader = "forge"

    def __init__(self, cache_dir: Path) -> None:
        self._cache = cache_dir

    def recommended_version(self, minecraft_version: str) -> str | None:
        promos = http_client.get_json(PROMOS_URL, self._cache)["promos"]
        return promos.get(f"{minecraft_version}-recommended") or promos.get(f"{minecraft_version}-latest")

    def installer_url(self, minecraft_version: str, loader_version: str) -> str:
        full = f"{minecraft_version}-{loader_version}"
        return f"https://maven.minecraftforge.net/net/minecraftforge/forge/{full}/forge-{full}-installer.jar"

    def argfile_dir(self, minecraft_version: str, loader_version: str) -> str:
        return f"libraries/net/minecraftforge/forge/{minecraft_version}-{loader_version}"
