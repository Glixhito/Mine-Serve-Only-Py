"""Pruebas del arranque automático. Sin Java, red ni PySide6."""
from types import SimpleNamespace

from database.connection import Database
from managers.autostart import AutostartStore, start_marked_servers
from repositories.settings_repository import SettingsRepository


class FakeRecord:
    def __init__(self, server_id, name):
        self.id = server_id
        self.name = name


class FakeServers:
    def list_servers(self):
        return [FakeRecord(1, "Alfa"), FakeRecord(2, "Beta"), FakeRecord(3, "Gamma")]


class FakeController:
    def __init__(self, failing):
        self.failing = failing
        self.started = []

    def start(self, server_id):
        if server_id in self.failing:
            raise PermissionError("Debes aceptar la EULA antes de iniciar el servidor.")
        self.started.append(server_id)


class FakeOperations:
    def __init__(self):
        self.rows = []

    def add(self, server_id, operation_type, status, message=""):
        self.rows.append((server_id, operation_type, status, message))


def test_autostart_flag_defaults_to_off_and_can_be_saved(tmp_path):
    db = Database(tmp_path / "manager.db")
    db.init_schema()
    store = AutostartStore(SettingsRepository(db))
    assert store.is_enabled(1) is False
    store.set_enabled(1, True)
    assert store.is_enabled(1) is True
    store.set_enabled(1, False)
    assert store.is_enabled(1) is False
    db.close()


def test_only_marked_servers_start_and_failures_are_reported(tmp_path):
    db = Database(tmp_path / "manager.db")
    db.init_schema()
    settings = SettingsRepository(db)
    store = AutostartStore(settings)
    store.set_enabled(1, True)
    store.set_enabled(2, True)  # Beta no tiene EULA: debe fallar y reportarse
    core = SimpleNamespace(settings=settings, servers=FakeServers(),
                           controller=FakeController(failing={2}), operations=FakeOperations())
    problems = start_marked_servers(core)
    assert core.controller.started == [1]
    assert problems == ["Beta: Debes aceptar la EULA antes de iniciar el servidor."]
    statuses = [(row[0], row[1], row[2]) for row in core.operations.rows]
    assert (1, "autoinicio", "solicitado") in statuses
    assert (2, "autoinicio", "fallido") in statuses
    db.close()