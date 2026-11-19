"""Arreglo automático de mods con Modrinth simulado y archivos JAR reales. Sin red."""
import json
import zipfile
from pathlib import Path

from integrations.modrinth_api import ModrinthError
from managers.mod_doctor import ModDoctor
from managers.mod_manager import ModManager


def _jar(folder: Path, file_name: str, mod_id: str, depends: dict | None = None) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(folder / file_name, "w") as archive:
        archive.writestr("fabric.mod.json", json.dumps({"id": mod_id, "version": "1.0", "depends": depends or {}}))


def _version(project_id: str, file_name: str, game_versions=("26.3",), loaders=("fabric",), mod_id=None) -> dict:
    return {"project_id": project_id, "game_versions": list(game_versions), "loaders": list(loaders),
            "dependencies": [], "version_number": "1", "mod_id": mod_id,
            "files": [{"filename": file_name, "url": f"https://cdn/{file_name}", "primary": True, "hashes": {}}]}


class FakeModrinth:
    def __init__(self, versions_by_sha=None, updates=None, found_deps=None):
        self.versions_by_sha = versions_by_sha or {}
        self.updates = updates or {}        # ID de proyecto -> plan de actualización
        self.found_deps = found_deps or {}  # ID de dependencia -> plan de instalación

    def installed_versions(self, sha_list):
        return {sha: self.versions_by_sha[sha] for sha in sha_list if sha in self.versions_by_sha}

    def plan_project(self, project_id, minecraft_version, loader, installed):
        if project_id not in self.updates:
            raise ModrinthError(f"No hay versión de {project_id} para {minecraft_version} ({loader}).")
        return self.updates[project_id]

    def plan_for_dependencies(self, dep_ids, minecraft_version, loader, installed):
        plan, not_found = [], []
        for dep in dep_ids:
            if dep in self.found_deps:
                plan += self.found_deps[dep]
            else:
                not_found.append(f"{dep}: no hay un proyecto con ese nombre en Modrinth")
        return plan, not_found

    def download_plan(self, plan, mods_dir: Path):
        mods_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for version in plan:
            name = version["files"][0]["filename"]
            if version.get("mod_id"):
                _jar(mods_dir, name, version["mod_id"])
            else:
                (mods_dir / name).write_bytes(b"jar")
            paths.append(mods_dir / name)
        return paths


def _sha(server: Path) -> dict[str, str]:
    return {mod.name: mod.sha1 for mod in ModManager().list_mods(server)}


def test_incompatible_mod_is_replaced_by_version_for_server(tmp_path):
    mods = tmp_path / "mods"
    _jar(mods, "nethermap-4.3.0+26.1.jar", "nethermap")
    sha = _sha(tmp_path)["nethermap-4.3.0+26.1.jar"]
    fake = FakeModrinth(
        versions_by_sha={sha: _version("NM", "nethermap-4.3.0+26.1.jar", game_versions=("26.1.x",))},
        updates={"NM": [_version("NM", "nethermap-4.4.0+26.3.jar", mod_id="nethermap")]},
    )
    report = ModDoctor(fake).run(tmp_path, "26.3", "fabric")
    assert (mods / "nethermap-4.4.0+26.3.jar").is_file()
    assert not (mods / "nethermap-4.3.0+26.1.jar").exists()
    assert (tmp_path / "mods_disabled" / "nethermap-4.3.0+26.1.jar").is_file()
    assert report.updated == ["nethermap-4.3.0+26.1.jar -> nethermap-4.4.0+26.3.jar"]


def test_mod_with_unavailable_dependency_is_disabled_not_deleted(tmp_path):
    mods = tmp_path / "mods"
    _jar(mods, "xaeroworldmap.jar", "xaeroworldmap", depends={"xaerolib": ">=1"})
    report = ModDoctor(FakeModrinth()).run(tmp_path, "26.3", "fabric")
    assert not (mods / "xaeroworldmap.jar").exists()
    assert (tmp_path / "mods_disabled" / "xaeroworldmap.jar").is_file()
    assert report.disabled and report.disabled[0].startswith("xaeroworldmap.jar: faltan dependencias")


def test_missing_dependency_is_installed_automatically(tmp_path):
    mods = tmp_path / "mods"
    _jar(mods, "epic.jar", "epic", depends={"fabric-api": "*"})
    fake = FakeModrinth(found_deps={"fabric-api": [_version("FAPI", "fabric-api-26.3.jar", mod_id="fabric-api")]})
    report = ModDoctor(fake).run(tmp_path, "26.3", "fabric")
    assert (mods / "fabric-api-26.3.jar").is_file()
    assert (mods / "epic.jar").is_file()
    assert report.installed == ["fabric-api-26.3.jar"]
    assert report.disabled == []


def test_dependents_of_a_disabled_mod_are_disabled_too(tmp_path):
    mods = tmp_path / "mods"
    _jar(mods, "a.jar", "a", depends={"xaerolib": "*"})
    _jar(mods, "b.jar", "b", depends={"a": "*"})
    report = ModDoctor(FakeModrinth()).run(tmp_path, "26.3", "fabric")
    assert sorted(p.name for p in mods.glob("*.jar")) == []
    assert {line.split(":")[0] for line in report.disabled} == {"a.jar", "b.jar"}


def test_compatible_mods_are_left_alone(tmp_path):
    mods = tmp_path / "mods"
    _jar(mods, "lithium.jar", "lithium")
    sha = _sha(tmp_path)["lithium.jar"]
    fake = FakeModrinth(versions_by_sha={sha: _version("LI", "lithium.jar")})
    report = ModDoctor(fake).run(tmp_path, "26.3", "fabric")
    assert (mods / "lithium.jar").is_file()
    assert report.lines() == ["Todos los mods activos son compatibles y tienen sus dependencias."]


def test_mod_without_version_for_server_is_disabled(tmp_path):
    mods = tmp_path / "mods"
    _jar(mods, "old.jar", "old")
    sha = _sha(tmp_path)["old.jar"]
    fake = FakeModrinth(versions_by_sha={sha: _version("OLD", "old.jar", game_versions=("1.20.1",))})
    report = ModDoctor(fake).run(tmp_path, "26.3", "fabric")
    assert (tmp_path / "mods_disabled" / "old.jar").is_file()
    assert report.disabled == ["old.jar: no tiene versión para Minecraft 26.3 (fabric)"]


def test_dependency_installed_but_not_detected_does_not_loop(tmp_path):
    mods = tmp_path / "mods"
    _jar(mods, "nether.jar", "nether", depends={"cloth-config2": "*"})
    fake = FakeModrinth(found_deps={"cloth-config2": [_version("CC", "cloth-config.jar", mod_id="cloth_config")]})
    report = ModDoctor(fake).run(tmp_path, "26.3", "fabric")
    assert (tmp_path / "mods_disabled" / "nether.jar").is_file()
    assert "se instalaron" in report.disabled[0]