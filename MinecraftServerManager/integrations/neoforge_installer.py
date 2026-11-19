"""Instalador de NeoForge (versiones que usan --installServer)."""
from __future__ import annotations

from integrations.loader_base import InstallerLoader


class NeoForgeInstaller(InstallerLoader):
    loader = "neoforge"

    def installer_url(self, minecraft_version: str, loader_version: str) -> str:
        return ("https://maven.neoforged.net/releases/net/neoforged/neoforge/"
                f"{loader_version}/neoforge-{loader_version}-installer.jar")

    def argfile_dir(self, minecraft_version: str, loader_version: str) -> str:
        return f"libraries/net/neoforged/neoforge/{loader_version}"
