"""Métricas del proceso del servidor (CPU, RAM y tiempo activo) con psutil."""
from __future__ import annotations

import time

import psutil

MB = 1024 * 1024


class ServerMonitor:
    def __init__(self) -> None:
        self._procs: dict[int, psutil.Process] = {}  # reutiliza objetos: cpu_percent necesita medición previa

    def snapshot(self, pid: int | None) -> dict:
        if pid is None:
            return {}
        try:
            proc = self._procs.get(pid)
            if proc is None:
                proc = self._procs[pid] = psutil.Process(pid)
                proc.cpu_percent(None)  # primera llamada: inicia la medición
            cores = psutil.cpu_count() or 1
            return {
                "cpu_pct": round(proc.cpu_percent(None) / cores, 1),  # porcentaje del equipo completo
                "ram_mb": proc.memory_info().rss // MB,
                "uptime_s": int(time.time() - proc.create_time()),
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            self._procs.pop(pid, None)
            return {}
