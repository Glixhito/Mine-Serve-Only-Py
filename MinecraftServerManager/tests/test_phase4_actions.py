"""Pruebas de acciones del servidor: edición, copia de configuración e historial. Sin red ni Java."""
from pathlib import Path

import pytest

from database.connection import Database
from managers.config_manager import ConfigManager
from managers.server_manager import ServerManager
from managers.version_manager import VersionManager
from repositories.operation_repository import OperationRepository
from repositories.server_repository import ServerRepository


def make_env(tmp_path):
    db = Database(tmp_path / "data" / "manager.db")
    db.init_schema()
    config = ConfigManager()
    manager = ServerManager(ServerRepository(db), tmp_path / "data" / "servers",
                            VersionManager(tmp_path / "data" / "cache"), config)
    return db, manager, config, OperationRepository(db)


def test_edit_changes_name_and_description(tmp_path):
    db, manager, _config, _ops = make_env(tmp_path)
    record = manager.create("Alfa", "1.21")
    manager.edit(record.id, name="Beta", description="Servidor de prueba")
    edited = manager.get(record.id)
    assert edited.name == "Beta"
    assert edited.description == "Servidor de prueba"
    db.close()


def test_edit_rejects_duplicate_name(tmp_path):
    db, manager, _config, _ops = make_env(tmp_path)
    manager.create("Alfa", "1.21")
    other = manager.create("Gamma", "1.21")
    with pytest.raises(ValueError):
        manager.edit(other.id, name="Alfa")
    db.close()


def test_copy_settings_keeps_properties_but_not_world(tmp_path):
    db, manager, config, _ops = make_env(tmp_path)
    source = manager.create("Origen", "1.21", online_mode=False)
    config.write(Path(source.server_path), {"motd": "Mi servidor", "max-players": "35"})
    target = manager.create("Copia", "1.21")
    manager.copy_settings(source.id, target.id)
    props = config.read(Path(target.server_path))
    assert props["motd"] == "Mi servidor"
    assert props["max-players"] == "35"
    assert props["online-mode"] == "false"
    assert manager.get(target.id).online_mode is False
    assert not (Path(target.server_path) / "world").exists()
    db.close()


def test_history_keeps_entries_after_server_deleted(tmp_path):
    db, manager, _config, ops = make_env(tmp_path)
    record = manager.create("Alfa", "1.21")
    ops.add(record.id, "iniciar", "solicitado")
    assert ops.recent(record.id)[0]["operation_type"] == "iniciar"
    manager.delete(record.id, confirmed=True)
    row = ops.recent()[0]
    assert row["server_id"] is None
    assert row["operation_type"] == "iniciar"
    db.close()


def test_history_for_missing_server_is_stored_without_reference(tmp_path):
    db, _manager, _config, ops = make_env(tmp_path)
    ops.add(999, "reiniciar", "fallido", "sin servidor")
    row = ops.recent()[0]
    assert row["server_id"] is None
    assert "[servidor eliminado]" in row["message"]
    db.close()