"""Seguimiento de jugadores conectados leyendo la consola del servidor. No consulta la red."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from database.models import ServerStatus

JOIN_RE = re.compile(r"(?P<name>[A-Za-z0-9_]{3,16}) joined the game")
LEAVE_RE = re.compile(r"(?P<name>[A-Za-z0-9_]{3,16}) left the game")
LIST_RE = re.compile(r"There are (?P<online>\d+) of a max of (?P<max>\d+) players online:(?P<names>.*)")


class PlayerTracker:
    def __init__(self, events) -> None:
        self._events = events
        self._online: dict[int, set[str]] = defaultdict(set)
        self._max: dict[int, int] = {}
        events.subscribe("server.log", self._on_log)
        events.subscribe("server.status_changed", self._on_status)

    def online(self, server_id: int) -> list[str]:
        return sorted(self._online.get(server_id, ()))

    def max_players(self, server_id: int) -> int | None:
        return self._max.get(server_id)

    def _on_log(self, server_id: int, line: str) -> None:
        if match := LIST_RE.search(line):  # respuesta del comando 'list': es la fuente más fiable
            names = {name.strip() for name in match.group("names").split(",") if name.strip()}
            self._online[server_id] = names
            self._max[server_id] = int(match.group("max"))
        elif match := JOIN_RE.search(line):
            self._online[server_id].add(match.group("name"))
        elif match := LEAVE_RE.search(line):
            self._online[server_id].discard(match.group("name"))
        else:
            return
        self._events.publish("players.changed", server_id=server_id)

    def _on_status(self, server_id: int, status: str) -> None:
        if status != ServerStatus.ACTIVE:  # sin servidor listo no hay jugadores conectados
            self._online.pop(server_id, None)
            self._events.publish("players.changed", server_id=server_id)


def read_name_list(server_dir: Path, filename: str) -> list[str]:
    """Nombres de whitelist.json, ops.json o banned-players.json. Vacío si no existe o está dañado."""
    path = server_dir / filename
    if not path.is_file():
        return []
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(entries, list):
        return []
    return sorted(entry["name"] for entry in entries if isinstance(entry, dict) and "name" in entry)