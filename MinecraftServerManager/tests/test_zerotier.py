"""Pruebas de ZeroTier con clientes simulados: no requieren red, ZeroTier instalado ni token real."""
from types import SimpleNamespace

import pytest

from core.event_manager import EventManager
from database.connection import Database
from integrations.zerotier_local import parse_network, parse_node_id
from managers.zerotier_manager import ZeroTierManager
from repositories.settings_repository import SettingsRepository

NETWORK = "8056c2e21c000001"


class FakeLocal:
    node = "a1b2c3d4e5"

    def __init__(self):
        self.authorized = False
        self.joined = []

    def join(self, network_id):
        self.joined.append(network_id)

    def node_id(self):
        return self.node

    def network_info(self, network_id):
        if self.authorized:
            return {"status": "OK", "ip": "10.147.20.5"}
        return {"status": "ACCESS_DENIED", "ip": None}


class FakeCentral:
    def __init__(self, local):
        self.local = local
        self.created = []
        self.authorized = []

    def create_network(self, name):
        self.created.append(name)
        return NETWORK

    def authorize_member(self, network_id, node_id):
        self.authorized.append((network_id, node_id))
        if node_id == self.local.node:
            self.local.authorized = True


class FakeOps:
    def __init__(self):
        self.rows = []

    def add(self, server_id, operation, status, message=""):
        self.rows.append((server_id, operation, status, message))


class FakeServers:
    def __init__(self, folder):
        self.folder = folder

    def get(self, server_id):
        return SimpleNamespace(server_path=str(self.folder))


class FakeConfig:
    def read(self, folder):
        return {"server-port": "25570"}


def make_manager(tmp_path, central, local):
    db = Database(tmp_path / "manager.db")
    db.init_schema()
    ops, events = FakeOps(), EventManager()
    manager = ZeroTierManager(SettingsRepository(db), FakeServers(tmp_path), ops, events, FakeConfig(),
                              central=central, local=local)
    return manager, db, ops, events


def test_parse_helpers():
    assert parse_node_id("200 info a1b2c3d4e5 1.14.6 ONLINE") == "a1b2c3d4e5"
    line = "200 listnetworks 8056c2e21c000001 MSM-alfa 52:54:00:12:34:56 OK PRIVATE ztabcdef 10.147.20.5/24"
    assert parse_network(line, NETWORK) == {"status": "OK", "ip": "10.147.20.5"}
    assert parse_network(line, "0000000000000000") == {"status": "NO_UNIDO", "ip": None}


def test_provision_creates_named_network(tmp_path):
    local = FakeLocal()
    central = FakeCentral(local)
    manager, db, _ops, _events = make_manager(tmp_path, central, local)
    assert manager.provision(SimpleNamespace(id=1, name="Alfa Beta")) == NETWORK
    assert central.created == ["MSM-alfa-beta"]
    assert manager.network_of(1) == NETWORK
    db.close()


def test_provision_without_token_does_not_break_creation(tmp_path):
    manager, db, ops, _events = make_manager(tmp_path, central=None, local=FakeLocal())
    assert manager.provision(SimpleNamespace(id=1, name="Alfa")) is None
    assert ops.rows[-1][2] == "fallido"
    db.close()


def test_join_authorizes_own_node_and_returns_ip(tmp_path):
    local = FakeLocal()
    central = FakeCentral(local)
    manager, db, _ops, _events = make_manager(tmp_path, central, local)
    manager.provision(SimpleNamespace(id=1, name="Alfa"))
    info = manager.join(1)
    assert info == {"status": "OK", "ip": "10.147.20.5"}
    assert local.joined == [NETWORK]
    assert central.authorized == [(NETWORK, "a1b2c3d4e5")]
    db.close()


def test_address_uses_ip_and_server_port(tmp_path):
    local = FakeLocal()
    central = FakeCentral(local)
    manager, db, _ops, _events = make_manager(tmp_path, central, local)
    manager.provision(SimpleNamespace(id=1, name="Alfa"))
    manager.join(1)
    assert manager.address(1)["minecraft"] == "10.147.20.5:25570"
    db.close()


def test_authorize_friend_validates_node_id(tmp_path):
    local = FakeLocal()
    central = FakeCentral(local)
    manager, db, _ops, _events = make_manager(tmp_path, central, local)
    manager.provision(SimpleNamespace(id=1, name="Alfa"))
    manager.authorize_friend(1, "F00DF00D00")
    assert central.authorized[-1] == (NETWORK, "f00df00d00")
    with pytest.raises(ValueError):
        manager.authorize_friend(1, "xyz")
    db.close()


def test_server_becoming_active_joins_network(tmp_path):
    local = FakeLocal()
    central = FakeCentral(local)
    manager, db, ops, events = make_manager(tmp_path, central, local)
    manager.provision(SimpleNamespace(id=1, name="Alfa"))
    events.publish("server.status_changed", server_id=1, status="activo")
    assert local.joined == [NETWORK]
    assert any(row[1] == "zerotier unir" and row[2] == "ok" for row in ops.rows)
    db.close()