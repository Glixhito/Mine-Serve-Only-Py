"""Preset de rendimiento: RAM fija y distancias moderadas, con respaldo previo y registro en el historial."""
from __future__ import annotations

from pathlib import Path

OPTIMAL_RAM_MB = 4096  # ajústalo si tu PC tiene menos memoria libre; el servidor y Windows la comparten
OPTIMAL_PROPERTIES = {
    "view-distance": "8",
    "simulation-distance": "6",
    "spawn-protection": "0",
    "difficulty": "normal",
}


class PresetManager:
    def __init__(self, servers, config, backups, operations) -> None:
        self._servers = servers
        self._config = config
        self._backups = backups
        self._operations = operations

    def describe(self) -> list[str]:
        lines = [f"RAM mínima y máxima: {OPTIMAL_RAM_MB} MB"]
        lines += [f"{key}: {value}" for key, value in OPTIMAL_PROPERTIES.items()]
        return lines

    def apply_optimal(self, server_id: int, *, running: bool) -> Path:
        """Crea un respaldo manual y luego aplica el preset. Nunca se aplica con el servidor encendido."""
        if running:
            raise RuntimeError("Detén el servidor antes de aplicar el preset.")
        record = self._servers.get(server_id)
        folder = Path(record.server_path)
        backup = self._backups.create(folder, running=False)
        self._servers.update_runtime(server_id, java_path=record.java_path or "",
                                     min_ram=OPTIMAL_RAM_MB, max_ram=OPTIMAL_RAM_MB)
        self._config.write(folder, dict(OPTIMAL_PROPERTIES))
        self._operations.add(server_id, "preset óptimo", "ok",
                             f"RAM {OPTIMAL_RAM_MB} MB; respaldo previo: {backup.name}")
        return backup