"""Pruebas del preset Óptimo: valores aplicados, respaldo previo y bloqueo con el servidor encendido. Sin red."""
from pathlib import Path

import pytest

from database.connection import Database
from managers.backup_manager import BackupManager
from managers.config_manager import ConfigManager
from managers.presets import OPTIMAL_RAM_MB, PresetManager
from managers.server_manager import ServerManager
from managers.version_manager import VersionManager
from repositories.operation_repository import OperationRepository
from repositories.server_repository import ServerRepository


def make(tmp_path):
    db = Database(tmp_path / "manager.db")
    db.init_schema()
    config = ConfigManager()
    servers = ServerManager(ServerRepository(db), tmp_path / "servers", VersionManager(tmp_path / "cache"), config)
    backups = BackupManager(tmp_path / "backups")
    operations = OperationRepository(db)
    presets = PresetManager(servers, config, backups, operations)
    return db, servers, config, backups, operations, presets


def test_preset_sets_values_and_keeps_other_settings(tmp_path):
    db, servers, config, _backups, _ops, presets = make(tmp_path)
    record = servers.create("Pack", "1.20.1", online_mode=False)
    servers.update_runtime(record.id, java_path="C:/java/bin/java.exe", min_ram=1024, max_ram=2048)
    config.write(Path(record.server_path), {"motd": "Mi servidor"})
    presets.apply_optimal(record.id, running=False)
    props = config.read(Path(record.server_path))
    assert props["view-distance"] == "8" and props["simulation-distance"] == "6"
    assert props["spawn-protection"] == "0"
    assert props["motd"] == "Mi servidor"
    assert props["online-mode"] == "false"
    updated = servers.get(record.id)
    assert updated.min_ram == OPTIMAL_RAM_MB and updated.max_ram == OPTIMAL_RAM_MB
    assert updated.java_path == "C:/java/bin/java.exe"
    db.close()


def test_preset_creates_manual_backup_first_and_logs_it(tmp_path):
    db, servers, _config, backups, ops, presets = make(tmp_path)
    record = servers.create("Pack", "1.20.1")
    backup = presets.apply_optimal(record.id, running=False)
    assert backup.exists()
    assert len(backups.list_backups(Path(record.server_path), kind="manual")) == 1
    assert ops.recent(record.id)[0]["operation_type"] == "preset óptimo"
    db.close()


def test_refuses_while_server_is_running(tmp_path):
    db, servers, config, _backups, _ops, presets = make(tmp_path)
    record = servers.create("Pack", "1.20.1")
    with pytest.raises(RuntimeError):
        presets.apply_optimal(record.id, running=True)
    assert config.read(Path(record.server_path))["view-distance"] == "10"  # el valor original no cambió
    db.close()