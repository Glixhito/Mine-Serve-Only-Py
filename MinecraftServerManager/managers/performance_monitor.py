"""Rendimiento en juego: cuenta los tirones recientes del log del servidor y da consejos según la memoria.

Un tirón es un síntoma: el log no dice la causa. Por eso los consejos se basan también en la memoria usada.
"""
from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass

# Formatos que escribe el servidor (versiones nuevas y antiguas).
LAG_RE = re.compile(r"Can't keep up!.*?Running (?P<ms>\d+)ms")
JOIN_RE = re.compile(r"\]: (?:System chat: )?(?P<name>[A-Za-z0-9_]{3,16}) joined the game\s*$")
LEAVE_RE = re.compile(r"\]: (?:System chat: )?(?P<name>[A-Za-z0-9_]{3,16}) left the game\s*$")
STOP_RE = re.compile(r"\]: Stopping (?:the )?server\s*$")
WINDOW_S = 600  # los tirones se cuentan en los últimos 10 minutos
MAX_EVENTS = 500


@dataclass(frozen=True)
class LagSummary:
    count: int
    worst_ms: int
    players: int


class PerformanceMonitor:
    def __init__(self, events, clock=time.monotonic) -> None:
        self._clock = clock
        self._lag: dict[int, deque[tuple[float, int]]] = {}
        self._players: dict[int, set[str]] = {}
        events.subscribe("server.log", self._on_log)

    def _on_log(self, server_id: int, line: str) -> None:
        if "Can't keep up" in line:
            match = LAG_RE.search(line)
            if match:
                events = self._lag.setdefault(server_id, deque(maxlen=MAX_EVENTS))
                events.append((self._clock(), int(match.group("ms"))))
            return
        if "joined the game" in line or "left the game" in line or "Stopping" in line:
            self._update_players(server_id, line)

    def _update_players(self, server_id: int, line: str) -> None:
        players = self._players.setdefault(server_id, set())
        if STOP_RE.search(line):
            players.clear()  # al apagar el servidor ya no hay nadie conectado
            return
        joined = JOIN_RE.search(line)
        if joined:
            players.add(joined.group("name"))
            return
        left = LEAVE_RE.search(line)
        if left:
            players.discard(left.group("name"))

    def summary(self, server_id: int) -> LagSummary:
        now = self._clock()
        recent = [ms for at, ms in self._lag.get(server_id, ()) if now - at <= WINDOW_S]
        return LagSummary(count=len(recent), worst_ms=max(recent, default=0),
                          players=len(self._players.get(server_id, ())))


def advice(summary: LagSummary, ram_mb: int | None, max_ram_mb: int) -> list[str]:
    """Consejos a partir de los tirones recientes y de la memoria usada."""
    if summary.count == 0:
        return ["Sin tirones en los últimos 10 minutos."]
    lines = [f"{summary.count} tirón(es) en los últimos 10 minutos; el peor retraso fue de "
             f"{summary.worst_ms / 1000:.1f} s."]
    if ram_mb is not None and max_ram_mb > 0 and ram_mb / max_ram_mb >= 0.9:
        lines.append("La memoria está casi llena. Sube la RAM máxima en Ajustes, dejando margen para el sistema.")
    else:
        lines.append("La memoria tiene margen, así que el problema suele estar en los mods recientes o en la "
                     "cantidad de entidades. Revisa esos mods y prueba a bajar la distancia de simulación "
                     "en server.properties.")
    return lines