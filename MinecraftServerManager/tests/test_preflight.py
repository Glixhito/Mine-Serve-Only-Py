"""Comprobación antes de iniciar: puertos ocupados y mundo bloqueado. Sin Minecraft y sin red externa."""
import os
import socket
from pathlib import Path

import pytest

from managers.preflight import (Conflict, check_before_start, format_conflicts,
                                is_locked, parse_port, port_in_use)


def _free_port(kind: str) -> int:
    family_type = socket.SOCK_STREAM if kind == "tcp" else socket.SOCK_DGRAM
    with socket.socket(socket.AF_INET, family_type) as probe:
        probe.bind(("", 0))
        return probe.getsockname()[1]


def _hold_lock(path: Path) -> int:
    """Mantiene un bloqueo sobre el archivo, como lo haría Minecraft, y devuelve el descriptor."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    fd = os.open(path, os.O_RDWR)
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def _release_lock(fd: int) -> None:
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)


def test_free_port_is_not_in_use():
    assert port_in_use(_free_port("tcp"), "tcp") is False


def test_busy_tcp_port_is_detected():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("", 0))
        server.listen()
        assert port_in_use(server.getsockname()[1], "tcp") is True


def test_busy_udp_port_is_detected():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as voice:
        voice.bind(("", 0))
        assert port_in_use(voice.getsockname()[1], "udp") is True


def test_missing_lock_file_is_not_locked(tmp_path):
    assert is_locked(tmp_path / "world" / "session.lock") is False


def test_stale_lock_file_after_normal_shutdown_is_not_locked(tmp_path):
    lock = tmp_path / "world" / "session.lock"
    lock.parent.mkdir(parents=True)
    lock.write_bytes(b"x")
    assert is_locked(lock) is False


def test_lock_held_by_another_process_is_detected(tmp_path):
    lock = tmp_path / "world" / "session.lock"
    fd = _hold_lock(lock)
    try:
        assert is_locked(lock) is True
    finally:
        _release_lock(fd)
    assert is_locked(lock) is False


def test_everything_free_has_no_conflicts(tmp_path):
    conflicts = check_before_start(tmp_path, server_port=_free_port("tcp"),
                                   voice_port=_free_port("udp"))
    assert conflicts == []


def test_busy_server_port_is_reported(tmp_path):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("", 0))
        server.listen()
        conflicts = check_before_start(tmp_path, server_port=server.getsockname()[1],
                                       voice_port=_free_port("udp"))
    assert [c.what for c in conflicts] == ["puerto del servidor"]


def test_busy_voice_port_is_reported(tmp_path):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as voice:
        voice.bind(("", 0))
        conflicts = check_before_start(tmp_path, server_port=_free_port("tcp"),
                                       voice_port=voice.getsockname()[1])
    assert [c.what for c in conflicts] == ["chat de voz"]


def test_locked_world_is_reported_and_clears_after_release(tmp_path):
    lock = tmp_path / "mi-mundo" / "session.lock"
    fd = _hold_lock(lock)
    try:
        conflicts = check_before_start(tmp_path, server_port=_free_port("tcp"),
                                       world_name="mi-mundo", voice_port=_free_port("udp"))
        assert [c.what for c in conflicts] == ["mundo"]
    finally:
        _release_lock(fd)
    assert check_before_start(tmp_path, server_port=_free_port("tcp"),
                              world_name="mi-mundo", voice_port=_free_port("udp")) == []


def test_already_running_server_is_reported_alone(tmp_path):
    conflicts = check_before_start(tmp_path, server_port=25565, already_running=True)
    assert conflicts == [Conflict("servidor", "Este servidor ya está en ejecución.")]


def test_parse_port_uses_default_for_invalid_values():
    assert parse_port("25566", 25565) == 25566
    assert parse_port("abc", 25565) == 25565
    assert parse_port(None, 25565) == 25565
    assert parse_port("70000", 25565) == 25565


def test_format_conflicts_lists_each_reason():
    text = format_conflicts([Conflict("mundo", "Motivo uno"), Conflict("chat de voz", "Motivo dos")])
    assert "• Motivo uno" in text and "• Motivo dos" in text