"""Pruebas de la semilla y el tipo de mundo. Sin red ni Java."""
from pathlib import Path

import pytest

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


def test_seed_and_level_type_are_written(tmp_path):
    db, manager = make(tmp_path)
    record = manager.create("Mundo", "1.20.1")
    manager.set_world(record.id, "  12345  ", "minecraft:flat")
    props = ConfigManager().read(Path(record.server_path))
    assert props["level-seed"] == "12345"
    assert props["level-type"] == "minecraft:flat"
    db.close()


def test_invalid_level_type_is_rejected(tmp_path):
    db, manager = make(tmp_path)
    record = manager.create("Mundo", "1.20.1")
    with pytest.raises(ValueError):
        manager.set_world(record.id, "", "minecraft:nope")
    db.close()


def test_seed_cannot_change_once_world_exists(tmp_path):
    db, manager = make(tmp_path)
    record = manager.create("Mundo", "1.20.1")
    (Path(record.server_path) / "world").mkdir()
    with pytest.raises(ValueError):
        manager.set_world(record.id, "999", "minecraft:normal")
    db.close()