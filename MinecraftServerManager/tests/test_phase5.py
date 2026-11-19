"""Pruebas de respaldos automáticos, retención y políticas. Sin red, Java ni PySide6."""
from datetime import datetime, timedelta, timezone

import pytest

from database.connection import Database
from managers.backup_manager import BackupManager
from managers.backup_policy import BackupPolicy, BackupPolicyStore
from repositories.settings_repository import SettingsRepository


def make_server(tmp_path, name="mi-server"):
    server = tmp_path / "servers" / name
    (server / "world").mkdir(parents=True)
    (server / "world" / "level.dat").write_text("datos")
    (server / "server.properties").write_text("motd=x")
    return server


def test_retention_removes_only_old_automatic_backups(tmp_path):
    server = make_server(tmp_path)
    manager = BackupManager(tmp_path / "backups")
    manual = manager.create(server, running=False)
    for _ in range(4):
        manager.create(server, running=False, automatic=True)
    removed = manager.prune_automatic(server, keep=2)
    assert len(removed) == 2
    assert len(manager.list_backups(server, kind="auto")) == 2
    assert manual.exists()  # un respaldo manual nunca se borra por retención


def test_list_by_kind(tmp_path):
    server = make_server(tmp_path)
    manager = BackupManager(tmp_path / "backups")
    manager.create(server, running=False)
    manager.create(server, running=False, automatic=True)
    assert len(manager.list_backups(server)) == 2
    assert len(manager.list_backups(server, kind="manual")) == 1
    assert len(manager.list_backups(server, kind="auto")) == 1


def test_delete_only_backups_of_this_server(tmp_path):
    server = make_server(tmp_path)
    other = make_server(tmp_path, "otro")
    manager = BackupManager(tmp_path / "backups")
    foreign = manager.create(other, running=False)
    with pytest.raises(FileNotFoundError):
        manager.delete(server, foreign)
    assert foreign.exists()


def test_policy_due_logic():
    now = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
    assert BackupPolicy(enabled=False).is_due(now) is False
    assert BackupPolicy(enabled=True, last_run=None).is_due(now) is True
    recent = (now - timedelta(hours=3)).isoformat()
    assert BackupPolicy(enabled=True, interval_hours=6, last_run=recent).is_due(now) is False
    old = (now - timedelta(hours=7)).isoformat()
    assert BackupPolicy(enabled=True, interval_hours=6, last_run=old).is_due(now) is True


def test_policy_roundtrip_and_validation(tmp_path):
    db = Database(tmp_path / "manager.db")
    db.init_schema()
    store = BackupPolicyStore(SettingsRepository(db))
    store.save(1, BackupPolicy(enabled=True, interval_hours=6, keep=5))
    loaded = store.get(1)
    assert loaded.enabled and loaded.interval_hours == 6 and loaded.keep == 5
    assert store.get(2) == BackupPolicy()  # sin política guardada: valores por defecto
    with pytest.raises(ValueError):
        store.save(1, BackupPolicy(enabled=True, interval_hours=0, keep=5))
    db.close()