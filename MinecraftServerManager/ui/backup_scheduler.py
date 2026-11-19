"""Respaldos automáticos según la política de cada servidor.

Con el servidor en ejecución sigue el procedimiento seguro de Minecraft:
save-off -> save-all flush -> espera 'Saved the game' -> copia -> save-on.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QObject, QTimer

from ui.workers import run_async

CHECK_MS = 60_000
SAVE_TIMEOUT_MS = 90_000
SAVED_MARKER = "Saved the game"
OP = "respaldo automático"


class BackupScheduler(QObject):
    def __init__(self, core, parent=None) -> None:
        super().__init__(parent)
        self._core = core
        self._busy: set[int] = set()
        self._waiting: dict[int, QTimer] = {}
        core.events.subscribe("server.log", self._on_log)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.check_due)
        self._timer.start(CHECK_MS)

    def check_due(self) -> None:
        now = datetime.now(timezone.utc)
        for record in self._core.servers.list_servers():
            if record.id not in self._busy and self._core.policies.get(record.id).is_due(now):
                self._start(record.id)

    def _folder(self, server_id: int) -> Path:
        return Path(self._core.servers.get(server_id).server_path)

    def _start(self, server_id: int) -> None:
        self._busy.add(server_id)
        folder = self._folder(server_id)
        if not self._core.controller.is_running(server_id):
            self._backup(server_id, folder, running=False)
            return
        try:
            self._core.controller.send_command(server_id, "save-off")
            self._core.controller.send_command(server_id, "save-all flush")
        except (RuntimeError, ValueError) as error:
            self._finish(server_id, folder, running=True, error=str(error))
            return
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._save_timeout(server_id, folder))
        timer.start(SAVE_TIMEOUT_MS)
        self._waiting[server_id] = timer

    def _on_log(self, server_id: int, line: str) -> None:
        timer = self._waiting.get(server_id)
        if timer is not None and SAVED_MARKER in line:
            timer.stop()
            del self._waiting[server_id]
            self._backup(server_id, self._folder(server_id), running=True)

    def _save_timeout(self, server_id: int, folder: Path) -> None:
        self._waiting.pop(server_id, None)
        self._finish(server_id, folder, running=True, error="Minecraft no confirmó el guardado a tiempo.")

    def _backup(self, server_id: int, folder: Path, running: bool) -> None:
        run_async(
            lambda: self._core.backups.create(folder, running=False, automatic=True),
            lambda path: self._finish(server_id, folder, running, path=path),
            lambda error: self._finish(server_id, folder, running, error=error),
        )

    def _finish(self, server_id: int, folder: Path, running: bool,
                path: Path | None = None, error: str | None = None) -> None:
        if running:
            self._send(server_id, "save-on")
        self._busy.discard(server_id)
        policy = self._core.policies.get(server_id)
        policy.last_run = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._core.policies.save(server_id, policy)
        if path is not None:
            removed = self._core.backups.prune_automatic(folder, policy.keep)
            self._core.operations.add(server_id, OP, "ok", f"{path.name}; retirados: {len(removed)}")
        else:
            self._core.operations.add(server_id, OP, "fallido", error or "error desconocido")

    def _send(self, server_id: int, command: str) -> None:
        try:
            self._core.controller.send_command(server_id, command)
        except (RuntimeError, ValueError):
            pass