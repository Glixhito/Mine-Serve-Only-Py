"""Pruebas de respaldos, administración de jugadores, monitor y red. No requieren Java ni red."""
import pytest

from managers.backup_manager import BackupError, BackupManager
from managers.player_admin import PlayerAdmin
from managers.server_monitor import ServerMonitor
from utils.network import port_is_free


def test_backup_restore_roundtrip(tmp_path):
    server = tmp_path / "servers" / "mi-server"
    (server / "world").mkdir(parents=True)
    (server / "world" / "level.dat").write_text("v1")
    (server / "server.properties").write_text("max-players=20")
    (server / "logs").mkdir()
    (server / "logs" / "latest.log").write_text("registro")
    manager = BackupManager(tmp_path / "backups")

    backup = manager.create(server, running=False)
    (server / "world" / "level.dat").write_text("v2")
    manager.restore(backup, server, running=False)

    assert (server / "world" / "level.dat").read_text() == "v1"
    assert (server / "logs" / "latest.log").exists()      # los registros se conservan
    assert len(manager.list_backups(server)) == 2         # incluye el respaldo de seguridad


def test_backups_of_similar_names_are_not_mixed(tmp_path):
    manager = BackupManager(tmp_path / "backups")
    (tmp_path / "mi").mkdir()
    (tmp_path / "mi-server").mkdir()
    manager.create(tmp_path / "mi-server", running=False)
    assert manager.list_backups(tmp_path / "mi") == []


def test_backup_refused_while_running(tmp_path):
    server = tmp_path / "s"
    server.mkdir()
    with pytest.raises(BackupError):
        BackupManager(tmp_path / "b").create(server, running=True)


def test_player_names_are_validated():
    class FakeController:
        sent = None

        def send_command(self, server_id, command):
            self.sent = command

    controller = FakeController()
    admin = PlayerAdmin(controller)
    admin.run(1, "op", "Steve")
    assert controller.sent == "op Steve"
    with pytest.raises(ValueError):
        admin.run(1, "op", "bad name; stop")


def test_monitor_without_process_returns_empty():
    assert ServerMonitor().snapshot(None) == {}


def test_port_check_returns_boolean():
    assert port_is_free(0) is True  # el puerto 0 pide un puerto libre al sistema
