"""Pruebas del núcleo: validaciones, Java, configuración y repositorio. Ejecutar: python -m pytest"""
import pytest

from database.connection import Database
from database.models import ServerRecord
from managers.config_manager import ConfigManager
from managers.java_manager import JavaInstall, JavaManager, required_java_major
from repositories.server_repository import ServerRepository
from utils import validators


def test_int_range_rejects_out_of_range():
    assert validators.int_in_range("25565", 1, 65535) == "25565"
    with pytest.raises(ValueError):
        validators.int_in_range("70000", 1, 65535)


def test_ensure_inside_blocks_traversal(tmp_path):
    base = tmp_path / "servers"
    base.mkdir()
    with pytest.raises(PermissionError):
        validators.ensure_inside(base, base / ".." / "otra")


def test_mc_version_parsing():
    assert validators.parse_mc_version("1.20.4") == (1, 20, 4)
    assert validators.parse_mc_version("24w14a") is None


def test_required_java_major():
    assert required_java_major("1.16.5") == 8
    assert required_java_major("1.17.1") == 16
    assert required_java_major("1.20.4") == 17
    assert required_java_major("1.21") == 21


def test_java_too_old_is_rejected():
    ok, _ = JavaManager().check_compatibility(JavaInstall("java", 17, "x"), "1.21")
    assert not ok


def test_config_validates_and_keeps_backup(tmp_path):
    config = ConfigManager()
    config.create_default(tmp_path, online_mode=False)
    assert config.read(tmp_path)["online-mode"] == "false"
    config.write(tmp_path, {"max-players": "30"})
    assert config.read(tmp_path)["max-players"] == "30"
    assert list(tmp_path.glob("server.properties.*.bak"))
    with pytest.raises(ValueError):
        config.write(tmp_path, {"rcon.password": "x"})


def test_eula_requires_explicit_acceptance(tmp_path):
    with pytest.raises(PermissionError):
        ConfigManager().accept_eula(tmp_path, accepted=False)


def test_repository_round_trip(tmp_path):
    db = Database(tmp_path / "test.db")
    db.init_schema()
    repo = ServerRepository(db)
    record = repo.insert(ServerRecord(
        name="Prueba", minecraft_version="1.21", server_path=str(tmp_path / "p"),
        min_ram=1024, max_ram=2048,
    ))
    assert repo.get(record.id).name == "Prueba"
    db.close()
