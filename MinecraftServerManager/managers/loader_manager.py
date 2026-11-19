"""Instalación de cargadores (Fabric, Forge, NeoForge) y construcción del comando de arranque."""
from __future__ import annotations

import json
from pathlib import Path

from integrations.fabric_installer import FabricInstaller
from integrations.forge_installer import ForgeInstaller
from integrations.loader_base import InstallerLoader, LoaderError
from integrations.neoforge_installer import NeoForgeInstaller
from managers.java_manager import JavaManager
from managers.server_manager import SERVER_JAR, ServerManager
from utils import file_manager

LOADER_FILE = "loader.json"  # describe cómo arrancar; sin este archivo el servidor es Vanilla


def build_launch_args(min_ram: int, max_ram: int, server_dir: Path) -> list[str]:
    """Argumentos para java como lista (sin shell). loader.json indica el modo de arranque."""
    ram = [f"-Xms{min_ram}M", f"-Xmx{max_ram}M"]
    marker = server_dir / LOADER_FILE
    if marker.is_file():
        spec = json.loads(marker.read_text(encoding="utf-8"))
        if spec.get("mode") == "argfile":
            return [*ram, f"@{spec['target']}", "nogui"]
        return [*ram, "-jar", spec.get("target", SERVER_JAR), "nogui"]
    return [*ram, "-jar", SERVER_JAR, "nogui"]


class LoaderManager:
    def __init__(self, servers: ServerManager, java: JavaManager, cache_dir: Path) -> None:
        self._servers = servers
        self._java = java
        self._installers: dict[str, InstallerLoader] = {
            "fabric": FabricInstaller(cache_dir),
            "forge": ForgeInstaller(cache_dir),
            "neoforge": NeoForgeInstaller(),
        }

    def get(self, loader: str):
        if loader not in self._installers:
            raise ValueError(f"Cargador no soportado: {loader}")
        return self._installers[loader]

    def install(self, server_id: int, loader: str, loader_version: str) -> None:
        """Instala el cargador en la carpeta del servidor. Nunca sobrescribe un jar o cargador existente."""
        installer = self.get(loader)
        record = self._servers.get(server_id)
        folder = Path(record.server_path)
        if (folder / SERVER_JAR).exists() or (folder / LOADER_FILE).exists():
            raise FileExistsError("El servidor ya tiene un jar o un cargador; crea un servidor nuevo para cambiarlo.")
        if installer.needs_java:
            java = self._java.probe(record.java_path or "")
            if java is None:
                raise LoaderError("Selecciona una instalación de Java válida antes de instalar este cargador.")
            ok, message = self._java.check_compatibility(java, record.minecraft_version)
            if not ok:
                raise LoaderError(message)
        spec = installer.install(folder, record.minecraft_version, loader_version, record.java_path or "")
        marker = {"loader": loader, "loader_version": loader_version, **spec}
        file_manager.write_text_atomic(folder / LOADER_FILE, json.dumps(marker, indent=2))
        self._servers.set_loader(server_id, loader, loader_version)
