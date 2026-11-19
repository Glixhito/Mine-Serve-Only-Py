"""Pruebas de la Fase 2 sin red: metadatos, activar/desactivar, validaciones y argumentos de arranque."""
import json
import zipfile
from pathlib import Path

import pytest

from managers.loader_manager import LOADER_FILE, build_launch_args
from managers.mod_manager import ModError, ModManager


def make_jar(path: Path, entries: dict[str, str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return path


def test_fabric_metadata_and_missing_dependency(tmp_path):
    meta = {"id": "a", "version": "1.0", "depends": {"fabric-api": "*", "minecraft": "1.20.1"}}
    make_jar(tmp_path / "mods" / "a.jar", {"fabric.mod.json": json.dumps(meta)})
    manager = ModManager()
    (mod,) = manager.list_mods(tmp_path)
    assert mod.mod_id == "a" and mod.loader == "fabric"
    assert mod.depends == {"fabric-api"}
    assert any("fabric-api" in warning for warning in manager.validate([mod]))


def test_forge_toml_keeps_only_mandatory_mod_dependencies(tmp_path):
    toml = ('[[mods]]\nmodId = "b"\nversion = "2.0"\n'
            '[[dependencies.b]]\nmodId = "forge"\nmandatory = true\n'
            '[[dependencies.b]]\nmodId = "c"\nmandatory = false\n')
    make_jar(tmp_path / "mods" / "b.jar", {"META-INF/mods.toml": toml})
    (mod,) = ModManager().list_mods(tmp_path)
    assert mod.loader == "forge"
    assert mod.depends == frozenset()


def test_disable_and_enable_roundtrip(tmp_path):
    make_jar(tmp_path / "mods" / "x.jar", {"fabric.mod.json": json.dumps({"id": "x"})})
    manager = ModManager()
    manager.set_enabled(tmp_path, "x.jar", False, running=False)
    assert not (tmp_path / "mods" / "x.jar").exists()
    (mod,) = manager.list_mods(tmp_path)
    assert mod.enabled is False
    manager.set_enabled(tmp_path, "x.jar", True, running=False)
    assert (tmp_path / "mods" / "x.jar").exists()


def test_mods_cannot_change_while_running(tmp_path):
    make_jar(tmp_path / "mods" / "x.jar", {"fabric.mod.json": json.dumps({"id": "x"})})
    with pytest.raises(ModError):
        ModManager().set_enabled(tmp_path, "x.jar", False, running=True)


def test_identical_files_are_reported_as_duplicates(tmp_path):
    (tmp_path / "mods").mkdir()
    for name in ("d1.jar", "d2.jar"):
        (tmp_path / "mods" / name).write_bytes(b"not a zip")  # contenido idéntico, metadatos desconocidos
    manager = ModManager()
    warnings = manager.validate(manager.list_mods(tmp_path))
    assert any("Duplicado" in warning for warning in warnings)


def test_launch_args_follow_loader_marker(tmp_path):
    assert build_launch_args(1024, 2048, tmp_path)[-3:] == ["-jar", "server.jar", "nogui"]
    (tmp_path / LOADER_FILE).write_text(json.dumps({"mode": "argfile", "target": "libraries/x/unix_args.txt"}))
    assert build_launch_args(1024, 2048, tmp_path)[-2:] == ["@libraries/x/unix_args.txt", "nogui"]
