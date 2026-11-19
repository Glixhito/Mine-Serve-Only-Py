"""Pruebas de amigos y conexión (directa o por relevo) de ZeroTier. Sin red ni ZeroTier instalado."""
from types import SimpleNamespace

import pytest

from core.event_manager import EventManager
from database.connection import Database
from integrations.zerotier_local import parse_peers
from managers.zerotier_manager import ZeroTierManager
from repositories.settings_repository import SettingsRepository

NETWORK = "743993800f03e6bd"
SAMPLE = """200 listpeers a1b2c3d4e5 203.0.113.7/9993 27 1.14.6 LEAF
200 listpeers f00df00d00 - 85 1.14.6 LEAF"""


class FakeLocal:
    def __init__(self, peers):
        self._peers = peers

    def peers(self):
        if self._peers is None:
            raise RuntimeError("ZeroTier no está instalado en este equipo.")
        return self._peers


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


def make(tmp_path, peers):
    db = Database(tmp_path / "manager.db")
    db.init_schema()
    manager = ZeroTierManager(SettingsRepository(db), FakeServers(), FakeOps(), EventManager(),
                              FakeConfig(), central=None, local=FakeLocal(peers))
    manager.set_network(1, NETWORK)
    return manager, db


def test_parse_peers_direct_and_relay():
    assert parse_peers(SAMPLE) == {
        "a1b2c3d4e5": {"route": "directo", "latency": 27},
        "f00df00d00": {"route": "relevo", "latency": 85},
    }


def test_register_and_list_friends(tmp_path):
    manager, db = make(tmp_path, parse_peers(SAMPLE))
    manager.register_friend(1, "A1B2C3D4E5", "Ana")
    assert manager.friends(1) == [{"node": "a1b2c3d4e5", "name": "Ana"}]
    db.close()


def test_friend_status_shows_direct_or_relay(tmp_path):
    manager, db = make(tmp_path, parse_peers(SAMPLE))
    manager.register_friend(1, "a1b2c3d4e5", "Ana")
    manager.register_friend(1, "f00df00d00", "Luis")
    status = {row["name"]: row for row in manager.friends_status(1)}
    assert status["Ana"]["route"] == "directo" and status["Ana"]["latency"] == 27
    assert status["Luis"]["route"] == "relevo" and status["Luis"]["latency"] == 85
    db.close()


def test_friend_not_seen_is_offline(tmp_path):
    manager, db = make(tmp_path, parse_peers(SAMPLE))
    manager.register_friend(1, "0123456789", "Sofi")
    assert manager.friends_status(1)[0]["route"] == "sin conexión"
    db.close()


def test_status_unknown_when_zerotier_is_missing(tmp_path):
    manager, db = make(tmp_path, None)
    manager.register_friend(1, "0123456789", "Sofi")
    assert manager.friends_status(1)[0]["route"] == "desconocido"
    db.close()


def test_remove_friend_and_reject_invalid_node(tmp_path):
    manager, db = make(tmp_path, parse_peers(SAMPLE))
    manager.register_friend(1, "a1b2c3d4e5", "Ana")
    manager.remove_friend(1, "a1b2c3d4e5")
    assert manager.friends(1) == []
    with pytest.raises(ValueError):
        manager.register_friend(1, "xyz", "Nadie")
    db.close()