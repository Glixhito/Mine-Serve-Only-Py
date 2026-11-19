"""Dependencias faltantes: Fabric API cubre módulos fabric-*, y la resolución usa slugs exactos. Sin red."""
from pathlib import Path

from integrations.modrinth_api import ModrinthClient
from managers.mod_manager import ModInfo, ModManager


def _mod(name: str, mod_id: str, depends: set[str], enabled: bool = True, sha1: str | None = None) -> ModInfo:
    return ModInfo(path=Path(name), mod_id=mod_id, version="1", loader="fabric",
                   depends=frozenset(depends), sha1=sha1 or name, enabled=enabled)


def test_missing_dependency_is_reported_with_mod_name():
    mods = [_mod("geophilic.jar", "geophilic", {"fabric-api"})]
    assert ModManager().missing_dependencies(mods) == {"geophilic.jar": {"fabric-api"}}


def test_fabric_module_is_covered_when_fabric_api_is_active():
    mods = [_mod("fabric-api.jar", "fabric-api", set()),
            _mod("epic.jar", "epic", {"fabric-resource-loader-v0"})]
    assert ModManager().missing_dependencies(mods) == {}


def test_fabric_module_is_missing_without_fabric_api():
    mods = [_mod("epic.jar", "epic", {"fabric-resource-loader-v0"})]
    assert ModManager().missing_dependencies(mods) == {"epic.jar": {"fabric-resource-loader-v0"}}


def test_disabled_mods_are_ignored():
    mods = [_mod("fabric-api.jar", "fabric-api", set(), enabled=False),
            _mod("geophilic.jar", "geophilic", {"fabric-api"})]
    assert ModManager().missing_dependencies(mods) == {"geophilic.jar": {"fabric-api"}}


def test_validate_keeps_the_same_message_format():
    mods = [_mod("geophilic.jar", "geophilic", {"fabric-api"})]
    assert ModManager().validate(mods) == ["geophilic.jar necesita: fabric-api"]


def _client_with(projects: dict, versions: dict) -> ModrinthClient:
    client = ModrinthClient(Path("."))
    client.project_by_slug = lambda slug: projects.get(slug)
    client.project_versions = lambda pid, mc, loader: versions.get(pid, [])
    client.search = lambda *args, **kwargs: []  # sin red en pruebas
    return client


def test_plan_resolves_fabric_module_to_fabric_api():
    client = _client_with(
        {"fabric-api": {"id": "P7dR8mSH", "slug": "fabric-api"}},
        {"P7dR8mSH": [{"project_id": "P7dR8mSH", "dependencies": [], "files": [{"url": "u", "filename": "a.jar"}]}]},
    )
    plan, not_found = client.plan_for_dependencies(["fabric-resource-loader-v0"], "26.3", "fabric", set())
    assert [v["project_id"] for v in plan] == ["P7dR8mSH"]
    assert not_found == []


def test_plan_skips_projects_already_installed():
    client = _client_with({"fabric-api": {"id": "P7dR8mSH", "slug": "fabric-api"}}, {})
    plan, not_found = client.plan_for_dependencies(["fabric-api"], "26.3", "fabric", {"P7dR8mSH"})
    assert plan == [] and not_found == []


def test_unknown_or_mismatched_slug_is_not_installed():
    client = _client_with({"cloth-config": {"id": "X", "slug": "something-else"}}, {})
    plan, not_found = client.plan_for_dependencies(["cloth-config", "nope"], "26.3", "fabric", set())
    assert plan == []
    assert [item.split(":")[0] for item in not_found] == ["cloth-config", "nope"]


def test_bundled_mixinextras_is_not_a_missing_dependency(tmp_path):
    import json
    import zipfile
    mods = tmp_path / "mods"
    mods.mkdir()
    with zipfile.ZipFile(mods / "lithium.jar", "w") as archive:
        archive.writestr("fabric.mod.json", json.dumps({
            "id": "lithium", "version": "0.26.3",
            "depends": {"mixinextras": ">=0.5", "fabricloader": ">=0.14"}}))
    found = ModManager().list_mods(tmp_path)
    assert "mixinextras" not in found[0].depends
    assert ModManager().missing_dependencies(found) == {}


def test_dependency_bundled_inside_the_jar_is_not_missing(tmp_path):
    import io
    import json
    import zipfile
    nested = io.BytesIO()
    with zipfile.ZipFile(nested, "w") as inner:
        inner.writestr("fabric.mod.json", json.dumps({"id": "xaerolib", "version": "1.0"}))
    mods = tmp_path / "mods"
    mods.mkdir()
    with zipfile.ZipFile(mods / "xaeroworldmap.jar", "w") as archive:
        archive.writestr("fabric.mod.json", json.dumps({
            "id": "xaeroworldmap", "version": "1.47.2", "depends": {"xaerolib": ">=1"}}))
        archive.writestr("META-INF/jars/xaerolib.jar", nested.getvalue())
    found = ModManager().list_mods(tmp_path)
    assert "xaerolib" in found[0].provides
    assert ModManager().missing_dependencies(found) == {}