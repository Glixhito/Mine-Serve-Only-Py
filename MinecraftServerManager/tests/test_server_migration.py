"""Migración de servidores: las rutas antiguas pasan a la copia instalada. Sin interfaz, sin red."""
from dataclasses import dataclass
from pathlib import Path

from managers.server_migration import repair_server_paths


@dataclass
class Rec:
    id: int
    name: str
    server_path: str


class FakeRepo:
    def __init__(self, records) -> None:
        self.records = list(records)

    def list_all(self):
        return list(self.records)

    def update(self, record) -> None:
        self.records = [record if item.id == record.id else item for item in self.records]


def test_old_project_path_moves_to_installed_copy(tmp_path):
    servers = tmp_path / "instalada" / "servers"
    (servers / "mi-mundo").mkdir(parents=True)
    old = tmp_path / "proyecto" / "data" / "servers" / "mi-mundo"  # ya no existe
    repo = FakeRepo([Rec(1, "Mi mundo", str(old))])
    fixed, missing = repair_server_paths(repo, servers)
    assert fixed == ["Mi mundo"] and missing == []
    assert Path(repo.records[0].server_path) == (servers / "mi-mundo").resolve()


def test_installed_copy_wins_even_if_old_folder_still_exists(tmp_path):
    servers = tmp_path / "instalada" / "servers"
    (servers / "x").mkdir(parents=True)
    old = tmp_path / "proyecto" / "x"
    old.mkdir(parents=True)
    repo = FakeRepo([Rec(1, "X", str(old))])
    repair_server_paths(repo, servers)
    assert Path(repo.records[0].server_path) == (servers / "x").resolve()


def test_correct_path_is_left_alone(tmp_path):
    servers = tmp_path / "servers"
    (servers / "y").mkdir(parents=True)
    repo = FakeRepo([Rec(1, "Y", str((servers / "y").resolve()))])
    assert repair_server_paths(repo, servers) == ([], [])


def test_server_without_any_folder_is_reported(tmp_path):
    servers = tmp_path / "servers"
    servers.mkdir()
    repo = FakeRepo([Rec(1, "Z", str(tmp_path / "viejo" / "z"))])
    assert repair_server_paths(repo, servers) == ([], ["Z"])