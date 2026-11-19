"""Cachés de sesión: Java no se vuelve a ejecutar sin cambios y Modrinth no pregunta dos veces por el mismo archivo."""
import subprocess
from pathlib import Path

from integrations import http_client
from integrations.modrinth_api import ModrinthClient
from managers.java_manager import JavaManager


class _Result:
    stderr = 'openjdk version "25.0.5" 2025-10-21\n64-Bit Server VM'
    stdout = ""


def test_java_is_probed_once_while_the_executable_is_unchanged(tmp_path, monkeypatch):
    exe = tmp_path / "java.exe"
    exe.write_bytes(b"fake")
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a) or _Result())
    manager = JavaManager()
    first = manager.probe(str(exe))
    second = manager.probe(str(exe))
    assert first is not None and first.major == 25 and second == first
    assert len(calls) == 1


def test_java_is_probed_again_when_the_executable_changes(tmp_path, monkeypatch):
    exe = tmp_path / "java.exe"
    exe.write_bytes(b"fake")
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(a) or _Result())
    manager = JavaManager()
    manager.probe(str(exe))
    exe.write_bytes(b"fake but bigger")
    manager.probe(str(exe))
    assert len(calls) == 2


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeHttp:
    def __init__(self, known: dict) -> None:
        self.known = known
        self.requests: list[list[str]] = []

    def post(self, url, json):
        self.requests.append(json["hashes"])
        return _FakeResponse({sha: self.known[sha] for sha in json["hashes"] if sha in self.known})


def test_modrinth_asks_about_each_file_only_once(monkeypatch):
    fake = _FakeHttp({"a": {"project_id": "P1", "game_versions": ["26.3"], "loaders": ["fabric"]}})
    monkeypatch.setattr(http_client, "client", lambda: fake)
    client = ModrinthClient(Path("."))
    assert client.installed_versions(["a", "b"]) == {"a": {"project_id": "P1", "game_versions": ["26.3"],
                                                            "loaders": ["fabric"]}}
    assert client.installed_projects(["a"]) == {"a": "P1"}
    assert fake.requests == [["a", "b"]]


def test_unknown_files_are_not_asked_again(monkeypatch):
    fake = _FakeHttp({})
    monkeypatch.setattr(http_client, "client", lambda: fake)
    client = ModrinthClient(Path("."))
    assert client.installed_projects(["manual"]) == {}
    assert client.installed_projects(["manual"]) == {}
    assert fake.requests == [["manual"]]