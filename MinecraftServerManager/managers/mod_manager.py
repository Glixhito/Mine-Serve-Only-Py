"""Gestión de mods: metadatos leídos del JAR, caché por firma de archivo, activar/desactivar y validaciones."""
from __future__ import annotations

import io
import json
import os
import tomllib
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from utils import file_manager, validators

MODS_DIR = "mods"
DISABLED_DIR = "mods_disabled"
# Identificadores que aporta la plataforma: no son mods instalables ni dependencias faltantes.
PLATFORM_IDS = frozenset({"minecraft", "java", "fabricloader", "fabric", "forge", "neoforge", "fml", "mixinextras"})


class ModError(RuntimeError):
    """Operación no permitida en el estado actual, por ejemplo con el servidor en ejecución."""


@dataclass(frozen=True)
class ModInfo:
    path: Path
    mod_id: str
    version: str
    loader: str
    depends: frozenset[str]
    sha1: str
    enabled: bool
    provides: frozenset[str] = frozenset()  # IDs incluidos dentro del JAR

    @property
    def name(self) -> str:
        return self.path.name


def _parse_toml(text: str, loader: str) -> tuple[str, str, str, frozenset[str]]:
    data = tomllib.loads(text)
    mod = data["mods"][0]
    mod_id = mod["modId"]
    required = data.get("dependencies", {}).get(mod_id, [])
    depends = frozenset(d["modId"] for d in required
                        if d.get("mandatory") and d["modId"] not in PLATFORM_IDS)
    return mod_id, str(mod.get("version", "?")), loader, depends


def _read_metadata(jar: Path) -> tuple[str, str, str, frozenset[str]]:
    """Lee solo las entradas de metadatos del JAR; el resto del archivo no se descomprime."""
    try:
        with zipfile.ZipFile(jar) as archive:
            names = set(archive.namelist())
            if "fabric.mod.json" in names:
                data = json.loads(archive.read("fabric.mod.json"))
                depends = frozenset(data.get("depends", {})) - PLATFORM_IDS
                return data["id"], str(data.get("version", "?")), "fabric", depends
            for entry, loader in (("META-INF/neoforge.mods.toml", "neoforge"),
                                  ("META-INF/mods.toml", "forge")):
                if entry in names:
                    return _parse_toml(archive.read(entry).decode("utf-8"), loader)
    except (zipfile.BadZipFile, KeyError, ValueError, IndexError, tomllib.TOMLDecodeError):
        pass  # JAR dañado o metadatos incompletos: se trata como mod desconocido
    return jar.stem, "?", "desconocido", frozenset()


def _bundled_ids(jar: Path) -> frozenset[str]:
    """IDs que el JAR ya trae: mods dentro de META-INF/jars (jar-in-jar) y los declarados en "provides"."""
    ids: set[str] = set()
    try:
        with zipfile.ZipFile(jar) as archive:
            if "fabric.mod.json" in archive.namelist():
                data = json.loads(archive.read("fabric.mod.json"))
                ids.update(data.get("provides", []))
            for entry in archive.namelist():
                if entry.startswith("META-INF/jars/") and entry.endswith(".jar"):
                    with zipfile.ZipFile(io.BytesIO(archive.read(entry))) as nested:
                        if "fabric.mod.json" in nested.namelist():
                            ids.add(json.loads(nested.read("fabric.mod.json"))["id"])
    except (zipfile.BadZipFile, KeyError, ValueError, TypeError):
        pass  # JAR dañado: se usan solo los IDs que sí se pudieron leer
    return frozenset(ids)


class ModManager:
    def __init__(self) -> None:
        # Caché por ruta con firma (tamaño, mtime): un mod sin cambios no se vuelve a leer ni a hashear.
        self._cache: dict[Path, tuple[tuple[int, int], ModInfo]] = {}

    def list_mods(self, server_dir: Path) -> list[ModInfo]:
        mods: list[ModInfo] = []
        for folder, enabled in ((server_dir / MODS_DIR, True), (server_dir / DISABLED_DIR, False)):
            if folder.is_dir():
                mods += [self._info(jar, enabled) for jar in sorted(folder.glob("*.jar"))]
        return mods

    def _info(self, jar: Path, enabled: bool) -> ModInfo:
        stat = jar.stat()
        signature = (stat.st_size, stat.st_mtime_ns)
        cached = self._cache.get(jar)
        if cached and cached[0] == signature:
            return cached[1]
        mod_id, version, loader, depends = _read_metadata(jar)
        info = ModInfo(jar, mod_id, version, loader, depends, file_manager.sha1_of(jar), enabled, _bundled_ids(jar))
        self._cache[jar] = (signature, info)
        return info

    def set_enabled(self, server_dir: Path, jar_name: str, enabled: bool, *, running: bool) -> Path:
        """Mueve el JAR entre mods/ y mods_disabled/ con renombrado atómico (sin copiar)."""
        if running:
            raise ModError("Detén el servidor antes de activar o desactivar mods.")
        active, disabled = server_dir / MODS_DIR, server_dir / DISABLED_DIR
        source_dir, target_dir = (disabled, active) if enabled else (active, disabled)
        source = source_dir / jar_name
        validators.ensure_inside(source_dir, source)  # impide nombres con '..' o rutas ajenas
        if not source.is_file():
            raise FileNotFoundError(f"No existe el mod {jar_name}.")
        target_dir.mkdir(parents=True, exist_ok=True)
        destination = target_dir / jar_name
        if destination.exists():
            raise FileExistsError(f"Ya existe {jar_name} en el destino; no se sobrescribe.")
        os.replace(source, destination)
        self._cache.pop(source, None)
        return destination

    def delete(self, server_dir: Path, jar_name: str, *, running: bool, confirmed: bool) -> None:
        """Elimina un mod de mods/ o de mods_disabled/. Requiere servidor detenido y confirmación."""
        if running:
            raise ModError("Detén el servidor antes de eliminar mods.")
        if not confirmed:
            raise PermissionError("Eliminar un mod requiere confirmación explícita.")
        for folder in (server_dir / MODS_DIR, server_dir / DISABLED_DIR):
            target = folder / jar_name
            validators.ensure_inside(folder, target)
            if target.is_file():
                target.unlink()
                self._cache.pop(target, None)
                return
        raise FileNotFoundError(f"No existe el mod {jar_name}.")

    def validate(self, mods: list[ModInfo]) -> list[str]:
        """Advertencias: archivos idénticos, mismo id en varias versiones y dependencias ausentes."""
        active = [mod for mod in mods if mod.enabled]
        by_sha: dict[str, list[ModInfo]] = defaultdict(list)
        by_id: dict[str, list[ModInfo]] = defaultdict(list)
        for mod in active:
            by_sha[mod.sha1].append(mod)
            by_id[mod.mod_id].append(mod)
        warnings = [f"Duplicado (mismo contenido): {', '.join(m.name for m in group)}"
                    for group in by_sha.values() if len(group) > 1]
        warnings += [f"Varias versiones del mod '{mod_id}': {', '.join(m.name for m in group)}"
                     for mod_id, group in by_id.items() if len(group) > 1]
        warnings += [f"{name} necesita: {', '.join(sorted(missing))}"
                     for name, missing in self.missing_dependencies(mods).items()]
        return warnings

    def missing_dependencies(self, mods: list[ModInfo]) -> dict[str, set[str]]:
        """Nombre de archivo -> IDs de dependencias que no están activos.

        Se consideran cubiertos: los IDs de mods activos, los que van dentro de sus JAR
        (p. ej. XaeroLib dentro de Xaero's World Map en Fabric) y los módulos «fabric-*» si hay Fabric API.
        """
        active = [mod for mod in mods if mod.enabled]
        present = {mod.mod_id for mod in active}
        for mod in active:
            present |= mod.provides
        fabric_api = "fabric-api" in present
        result: dict[str, set[str]] = {}
        for mod in active:
            missing = {dep for dep in mod.depends
                       if dep not in present and not (fabric_api and dep.startswith("fabric-"))}
            if missing:
                result[mod.name] = missing
        return result