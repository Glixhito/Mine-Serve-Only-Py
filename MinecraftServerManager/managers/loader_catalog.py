"""Versiones de cargador que el diálogo ofrece, tomadas de cada proveedor. Así no hay que escribirlas a mano."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from integrations import http_client

PROMOS_URL = "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"
NEOFORGE_METADATA_URL = "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml"
FABRIC_META = "https://meta.fabricmc.net/v2/versions"


def forge_from_promos(promos: dict, minecraft_version: str) -> list[str]:
    """Versión recomendada primero y luego la más reciente, sin repetir."""
    found: list[str] = []
    for key in (f"{minecraft_version}-recommended", f"{minecraft_version}-latest"):
        value = promos.get(key)
        if value and value not in found:
            found.append(value)
    return found


def neoforge_prefix(minecraft_version: str) -> str:
    """NeoForge usa 'X.Y.build' para Minecraft 1.X.Y; en otros formatos usa la propia versión."""
    parts = minecraft_version.split(".")
    if parts[0] == "1" and len(parts) >= 2:
        return ".".join(parts[1:]) + "."
    return minecraft_version + "."


def neoforge_from_metadata(xml_text: str, minecraft_version: str) -> list[str]:
    """Versiones de NeoForge para esa versión de Minecraft, de la más nueva a la más antigua."""
    root = ET.fromstring(xml_text)
    versions = [node.text for node in root.iter("version") if node.text]
    prefix = neoforge_prefix(minecraft_version)
    return [version for version in reversed(versions) if version.startswith(prefix)]


def fabric_from_entries(items: list[dict]) -> list[str]:
    """Entradas tal como las devuelve Fabric. Las estables aparecen primero."""
    stable, unstable = [], []
    for item in items:
        info = item["loader"]
        (stable if info.get("stable") else unstable).append(info["version"])
    return stable + unstable


class LoaderCatalog:
    def __init__(self, cache_dir: Path) -> None:
        self._cache = cache_dir

    def versions(self, loader: str, minecraft_version: str) -> list[str]:
        if loader == "fabric":
            items = http_client.get_json(f"{FABRIC_META}/loader/{minecraft_version}", self._cache)
            return fabric_from_entries(items)
        if loader == "forge":
            promos = http_client.get_json(PROMOS_URL, self._cache)["promos"]
            return forge_from_promos(promos, minecraft_version)
        if loader == "neoforge":
            text = http_client.get_text_or_none(NEOFORGE_METADATA_URL)
            return neoforge_from_metadata(text, minecraft_version) if text else []
        return []