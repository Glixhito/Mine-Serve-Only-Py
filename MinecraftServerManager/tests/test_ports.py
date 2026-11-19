"""Pruebas de asignación automática de puertos: cada servidor recibe uno libre y distinto. Sin red ni Java."""
from pathlib import Path

from database.connection import Database
from managers.config_manager import ConfigManager
from managers.server_manager import ServerManager
from managers.version_manager import VersionManager
from repositories.server_repository import ServerRepository


def make(tmp_path):
    db = Database(tmp_path / "manager.db")
    db.init_schema()
    manager = ServerManager(ServerRepository(db), tmp_path / "servers",
                            VersionManager(tmp_path / "cache"), ConfigManager())
    return db, manager


def port_of(record):
    return int(ConfigManager().read(Path(record.server_path))["server-port"])


def test_each_new_server_gets_its_own_port(tmp_path):
    db, manager = make(tmp_path)
    first = manager.create("Alfa", "1.20.1")
    second = manager.create("Beta", "1.20.1")
    assert port_of(first) != port_of(second)
    assert port_of(first) >= 25565 and port_of(second) >= 25565
    db.close()


def test_allocate_skips_ports_used_by_servers(tmp_path):
    db, manager = make(tmp_path)
    record = manager.create("Alfa", "1.20.1")
    assert manager.allocate_port() != port_of(record)
    db.close()


def test_duplicate_gets_a_new_port(tmp_path):
    db, manager = make(tmp_path)
    source = manager.create("Origen", "1.20.1")
    target = manager.create("Copia", "1.20.1")
    manager.copy_settings(source.id, target.id)
    assert port_of(target) != port_of(source)
    db.close()