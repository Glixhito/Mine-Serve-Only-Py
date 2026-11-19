"""Pruebas de la red compartida: una sola red para todos los servidores; sale solo al apagar el último."""
from types import SimpleNamespace

from core.event_manager import EventManager
from database.connection import Database
from managers.zerotier_manager import ZeroTierManager
from repositories.settings_repository import SettingsRepository

NETWORK = "08752e18b12ad7b3"


class FakeLocal:
    def __init__(self):
        self.joined = []
        self.left = []

    def join(self, network_id):
        self.joined.append(network_id)

    def leave(self, network_id):
        self.left.append(network_id)

    def node_id(self):
        return "a1b2c3d4e5"

    def network_info(self, network_id):
        return {"status": "OK", "ip": "10.253.93.143"}


class FakeOps:
    def __init__(self):
        self.rows = []

    def add(self, server_id, operation, status, message=""):
        self.rows.append((server_id, operation, status, message))


class FakeServers:
    def get(self, server_id):
        return SimpleNamespace(server_path=f"/srv/{server_id}")


class FakeConfig:
    def read(self, folder):
        return {"server-port": "25565" if folder.name == "1" else "25566"}


def make(tmp_path):
    db = Database(tmp_path / "manager.db")
    db.init_schema()
    local, events = FakeLocal(), EventManager()
    manager = ZeroTierManager(SettingsRepository(db), FakeServers(), FakeOps(), events, FakeConfig(),
                              central=None, local=local)
    manager.set_network(1, NETWORK)
    return manager, db, local, events


def test_all_servers_share_one_network(tmp_path):
    manager, db, _local, _events = make(tmp_path)
    assert manager.network_of(1) == NETWORK
    assert manager.network_of(2) == NETWORK
    db.close()


def test_network_stays_while_any_server_runs(tmp_path):
    manager, db, local, events = make(tmp_path)
    events.publish("server.status_changed", server_id=1, status="activo")
    events.publish("server.status_changed", server_id=2, status="activo")
    events.publish("server.status_changed", server_id=1, status="detenido")
    assert local.left == []
    events.publish("server.status_changed", server_id=2, status="detenido")
    assert local.left == [NETWORK]
    db.close()


def test_each_server_address_uses_its_own_port(tmp_path):
    manager, db, _local, events = make(tmp_path)
    events.publish("server.status_changed", server_id=1, status="activo")
    assert manager.address(1)["minecraft"] == "10.253.93.143:25565"
    assert manager.address(2)["minecraft"] == "10.253.93.143:25566"
    db.close()