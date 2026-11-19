"""Pruebas de la whitelist: UUID offline, corrección de entradas y comandos según el modo. Sin red."""
import json
from types import SimpleNamespace

import pytest

from managers.player_admin import PlayerAdmin
from managers.whitelist_manager import WhitelistManager, offline_uuid

GLIXHITO_OFFLINE = "e27a52e4-f2d5-3ab2-a2c8-1dd55bcfa274"


class FakeController:
    def __init__(self, running):
        self.running = running
        self.sent = []

    def is_running(self, server_id):
        return self.running

    def send_command(self, server_id, command):
        if not self.running:
            raise RuntimeError("El servidor no está en ejecución.")
        self.sent.append(command)


class FakeServers:
    def __init__(self, folder, online):
        self._record = SimpleNamespace(server_path=str(folder), online_mode=online)

    def get(self, server_id):
        return self._record


def test_offline_uuid_matches_minecraft_value():
    assert offline_uuid("Glixhito") == GLIXHITO_OFFLINE


def test_add_replaces_premium_entry(tmp_path):
    (tmp_path / "whitelist.json").write_text(
        json.dumps([{"uuid": "11111111-2222-4333-8444-555555555555", "name": "Glixhito"}]), encoding="utf-8")
    WhitelistManager().add_offline(tmp_path, "Glixhito")
    entries = WhitelistManager().read(tmp_path)
    assert entries == [{"uuid": GLIXHITO_OFFLINE, "name": "Glixhito"}]


def test_add_is_case_insensitive_and_has_no_duplicates(tmp_path):
    manager = WhitelistManager()
    manager.add_offline(tmp_path, "Steve")
    manager.add_offline(tmp_path, "steve")
    assert len(manager.read(tmp_path)) == 1


def test_remove_and_not_found(tmp_path):
    manager = WhitelistManager()
    manager.add_offline(tmp_path, "Alex")
    manager.remove(tmp_path, "alex")
    assert manager.read(tmp_path) == []
    with pytest.raises(ValueError):
        manager.remove(tmp_path, "Alex")


def test_broken_file_is_reported(tmp_path):
    (tmp_path / "whitelist.json").write_text("no es json", encoding="utf-8")
    with pytest.raises(ValueError):
        WhitelistManager().read(tmp_path)


def test_offline_add_works_while_server_is_stopped(tmp_path):
    controller = FakeController(running=False)
    admin = PlayerAdmin(controller, None, FakeServers(tmp_path, online=False), WhitelistManager())
    admin.run(1, "whitelist_add", "Glixhito")
    assert WhitelistManager().read(tmp_path) == [{"uuid": GLIXHITO_OFFLINE, "name": "Glixhito"}]
    assert controller.sent == []


def test_offline_add_reloads_whitelist_when_running(tmp_path):
    controller = FakeController(running=True)
    admin = PlayerAdmin(controller, None, FakeServers(tmp_path, online=False), WhitelistManager())
    admin.run(1, "whitelist_add", "Glixhito")
    assert controller.sent == ["whitelist reload"]


def test_online_server_still_uses_command(tmp_path):
    controller = FakeController(running=True)
    admin = PlayerAdmin(controller, None, FakeServers(tmp_path, online=True), WhitelistManager())
    admin.run(1, "whitelist_add", "Steve")
    assert controller.sent == ["whitelist add Steve"]