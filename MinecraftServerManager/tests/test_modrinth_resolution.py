"""Resolución de dependencias y filtro de mods de servidor, con Modrinth simulado. Sin red."""
from pathlib import Path

from integrations import http_client
from integrations.modrinth_api import ModrinthClient, ModrinthError


def _client(projects: dict, versions: dict | None = None, search_hits: list | None = None) -> ModrinthClient:
    client = ModrinthClient(Path("."))
    client.project_by_slug = lambda slug: projects.get(slug)
    client.project_versions = lambda pid, mc, loader: (versions or {}).get(pid, [])
    client.search = lambda query, mc, loader, limit=20: search_hits or []
    return client


def test_hyphenated_slug_is_found_for_underscored_mod_id():
    client = _client({"cloth-config": {"id": "C1", "slug": "cloth-config", "title": "Cloth Config"}},
                     {"C1": [{"project_id": "C1", "dependencies": [], "files": [{"url": "u", "filename": "c.jar"}]}]})
    plan, not_found = client.plan_for_dependencies(["cloth_config"], "1.20.1", "forge", set())
    assert [v["project_id"] for v in plan] == ["C1"]
    assert not_found == []


def test_exact_search_match_is_used_when_slug_is_unknown():
    hit = {"project_id": "C1", "slug": "cloth-config", "title": "Cloth Config"}
    client = _client({}, {"C1": [{"project_id": "C1", "dependencies": [], "files": [{"url": "u", "filename": "c.jar"}]}]},
                     search_hits=[{"project_id": "X", "slug": "otro-mod"}, hit])
    plan, not_found = client.plan_for_dependencies(["cloth_config"], "1.20.1", "forge", set())
    assert [v["project_id"] for v in plan] == ["C1"]
    assert not_found == []


def test_similar_but_different_search_result_is_not_installed():
    client = _client({}, {}, search_hits=[{"project_id": "X", "slug": "cloth-config-extra"}])
    plan, not_found = client.plan_for_dependencies(["cloth_config"], "1.20.1", "forge", set())
    assert plan == []
    assert "no hay un proyecto" in not_found[0]


def test_missing_version_for_server_version_names_the_project():
    client = _client({"lithium": {"id": "L1", "slug": "lithium", "title": "Lithium"}}, {"L1": []})
    plan, not_found = client.plan_for_dependencies(["lithium"], "26.3", "fabric", set())
    assert plan == []
    assert "Lithium" in not_found[0] and "26.3" in not_found[0]


def test_dependency_that_only_has_version_id_is_resolved(monkeypatch):
    client = ModrinthClient(Path("."))
    client._project_of_version = lambda version_id: "P1" if version_id == "V1" else None
    client.project_versions = lambda pid, mc, loader: [{"project_id": pid, "dependencies": [], "files": []}]
    first = {"project_id": "A", "dependencies": [{"dependency_type": "required", "version_id": "V1"}]}
    plan = client._resolve_plan(first, "26.3", "fabric", set())
    assert [v["project_id"] for v in plan] == ["A", "P1"]


def test_missing_nested_dependency_is_reported_not_raised():
    client = _client({"a": {"id": "A", "slug": "a", "title": "Mod A"}},
                     {"A": [{"project_id": "A", "dependencies": [{"dependency_type": "required", "project_id": "B"}],
                             "files": []}]})
    plan, not_found = client.plan_for_dependencies(["a"], "26.3", "fabric", set())
    assert plan == []
    assert "Falta" in not_found[0]


def test_search_hides_client_only_mods(monkeypatch):
    def fake_get_json(url, cache, params=None):
        return {"hits": [{"slug": "solo-cliente", "server_side": "unsupported"},
                         {"slug": "servidor", "server_side": "required"}]}
    monkeypatch.setattr(http_client, "get_json", fake_get_json)
    hits = ModrinthClient(Path(".")).search("x", "26.3", "fabric")
    assert [hit["slug"] for hit in hits] == ["servidor"]