"""Pruebas del modo sin token (cuenta gratuita): red asignada a mano y autorización manual."""
from types import SimpleNamespace

import pytest

from core.event_manager import EventManager
from database.connection import Database
from integrations.zerotier_api import ZeroTierError
from managers.zerotier_manager import ZeroTierManager
from repositories.settings_repository import SettingsRepository


class FakeLocal:
    def __init__(self):
        self.joined = []

    def join(self, network_id):
        self.joined.append(network_id)

    def node_id(self):
        return "a1b2c3d4e5"

    def network_info(self, network_id):
        return {"status": "ACCESS_DENIED", "ip": None}


class FakeOps:
    def __init__(self):
        self.rows = []

    def add(self, server_id, operation, status, message=""):
        self.rows.append((server_id, operation, status, message))


class FakeServers:
    def get(self, server_id):
        return SimpleNamespace(server_path="unused")


class FakeConfig:
    def read(self, folder):
        return {"server-port": "25565"}


def make_manual_manager(tmp_path):
    db = Database(tmp_path / "manager.db")
    db.init_schema()
    local, ops, events = FakeLocal(), FakeOps(), EventManager()
    manager = ZeroTierManager(SettingsRepository(db), FakeServers(), ops, events, FakeConfig(),
                              central=None, local=local)
    return manager, db, local, ops, events


def test_set_network_accepts_manual_id(tmp_path):
    manager, db, _local, _ops, _events = make_manual_manager(tmp_path)
    manager.set_network(1, "743993800F03E6BD")
    assert manager.network_of(1) == "743993800f03e6bd"
    db.close()


def test_set_network_rejects_invalid_id(tmp_path):
    manager, db, _local, _ops, _events = make_manual_manager(tmp_path)
    with pytest.raises(ValueError):
        manager.set_network(1, "123")
    db.close()


def test_starting_without_token_joins_and_waits_for_manual_auth(tmp_path):
    manager, db, local, ops, events = make_manual_manager(tmp_path)
    manager.set_network(1, "743993800f03e6bd")
    events.publish("server.status_changed", server_id=1, status="activo")
    assert local.joined == ["743993800f03e6bd"]
    assert manager.join(1) == {"status": "ACCESS_DENIED", "ip": None}
    assert any(row[1] == "zerotier unir" and row[2] == "ok" for row in ops.rows)
    db.close()


def test_friend_authorization_needs_token(tmp_path):
    manager, db, _local, _ops, _events = make_manual_manager(tmp_path)
    manager.set_network(1, "743993800f03e6bd")
    with pytest.raises(ZeroTierError):
        manager.authorize_friend(1, "f00df00d00")
    db.close()