"""Comprobación antes de iniciar un servidor: puertos y mundo en uso por otro proceso."""
from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path

import psutil

VOICE_PORT = 24454  # chat de voz de Simple Voice Chat (UDP)


@dataclass(frozen=True)
class Conflict:
    what: str
    detail: str


def parse_port(value, default: int) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return default
    return port if 1 <= port <= 65535 else default


def port_in_use(port: int, kind: str = "tcp") -> bool:
    family_type = socket.SOCK_STREAM if kind == "tcp" else socket.SOCK_DGRAM
    try:
        with socket.socket(socket.AF_INET, family_type) as probe:
            probe.bind(("", port))
    except OSError:
        return True
    return False


def _owner(port: int, kind: str) -> str:
    wanted = socket.SOCK_STREAM if kind == "tcp" else socket.SOCK_DGRAM
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == port and conn.type == wanted and conn.pid:
                try:
                    name = psutil.Process(conn.pid).name()
                except psutil.Error:
                    name = "desconocido"
                return f" (lo usa «{name}», PID {conn.pid})"
    except (psutil.Error, OSError):
        pass
    return ""


def is_locked(path: Path) -> bool:
    """True si otro proceso mantiene el bloqueo del archivo (p. ej. session.lock de Minecraft)."""
    if not path.is_file():
        return False
    try:
        fd = os.open(path, os.O_RDWR)
    except OSError:
        return True
    try:
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError:
                return True
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            return False
        import fcntl
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def check_before_start(server_dir: Path, server_port: int, world_name: str = "world",
                       voice_port: int = VOICE_PORT, already_running: bool = False) -> list[Conflict]:
    if already_running:
        return [Conflict("servidor", "Este servidor ya está en ejecución.")]
    conflicts: list[Conflict] = []
    if port_in_use(server_port, "tcp"):
        conflicts.append(Conflict(
            "puerto del servidor",
            f"El puerto {server_port} (TCP) del servidor ya está en uso{_owner(server_port, 'tcp')}. "
            "Cierra ese programa o cambia el puerto en Ajustes."))
    if port_in_use(voice_port, "udp"):
        conflicts.append(Conflict(
            "chat de voz",
            f"El puerto {voice_port} (UDP) del chat de voz ya está en uso{_owner(voice_port, 'udp')}. "
            "Cierra ese programa o la otra copia del servidor."))
    if is_locked(server_dir / world_name / "session.lock"):
        conflicts.append(Conflict(
            "mundo",
            f"Otro proceso tiene abierto el mundo «{world_name}». "
            "Detén esa copia del servidor antes de iniciar."))
    return conflicts


def format_conflicts(conflicts: list[Conflict]) -> str:
    lines = ["No se puede iniciar el servidor por estos motivos:"]
    lines += [f"• {conflict.detail}" for conflict in conflicts]
    lines += ["", "Cierra el programa o la copia del servidor que lo usa y vuelve a intentar."]
    return "\n".join(lines)