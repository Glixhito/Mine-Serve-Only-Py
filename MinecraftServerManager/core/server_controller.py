"""Controlador de ejecución: valida requisitos, arranca y detiene procesos, publica estados."""
from __future__ import annotations

import logging
from pathlib import Path

from core.event_manager import EventManager
from core.process_manager import ProcessManager
from database.models import ServerStatus
from managers.config_manager import ConfigManager
from managers.java_manager import JavaManager
from managers.loader_manager import LOADER_FILE, build_launch_args
from managers.server_manager import SERVER_JAR, ServerManager

log = logging.getLogger(__name__)
READY_MARKER = "Done ("  # Minecraft imprime esta línea cuando el servidor está listo


class ServerController:
    def __init__(self, servers: ServerManager, config: ConfigManager,
                 java: JavaManager, events: EventManager) -> None:
        self._servers = servers
        self._config = config
        self._java = java
        self._events = events
        self._processes: dict[int, ProcessManager] = {}
        self._status: dict[int, str] = {}
        self._stop_requested: set[int] = set()
        self._restart_requested: set[int] = set()

    def status(self, server_id: int) -> str:
        return self._status.get(server_id, ServerStatus.STOPPED)

    def is_running(self, server_id: int) -> bool:
        process = self._processes.get(server_id)
        return process is not None and process.is_running()

    def start(self, server_id: int) -> None:
        """Verifica requisitos (jar, EULA, Java compatible) antes de lanzar el proceso."""
        if self.is_running(server_id):
            raise RuntimeError("El servidor ya está en ejecución.")
        record = self._servers.get(server_id)
        folder = Path(record.server_path)
        if not (folder / SERVER_JAR).is_file() and not (folder / LOADER_FILE).is_file():
            raise FileNotFoundError("Falta server.jar o el cargador: instálalo primero.")
        if not self._config.has_eula(folder):
            raise PermissionError("Debes aceptar la EULA antes de iniciar el servidor.")
        install = self._java.probe(record.java_path or "")
        if install is None:
            raise RuntimeError("Java no seleccionado o no válido.")
        ok, message = self._java.check_compatibility(install, record.minecraft_version)
        if not ok:
            raise RuntimeError(message)

        if server_id not in self._processes:
            self._processes[server_id] = self._create_process(server_id)
        args = build_launch_args(record.min_ram, record.max_ram, folder)
        self._processes[server_id].start(install.path, args, cwd=folder)
        self._set_status(server_id, ServerStatus.STARTING)
        log.info("Iniciando servidor %s", record.name)

    def stop(self, server_id: int, timeout_ms: int = 30_000) -> None:
        if self.is_running(server_id):
            self._stop_requested.add(server_id)
            self._processes[server_id].request_stop(timeout_ms)

    def send_command(self, server_id: int, command: str) -> None:
        if not self.is_running(server_id):
            raise RuntimeError("El servidor no está en ejecución.")
        if "\n" in command or "\r" in command:
            raise ValueError("El comando no puede contener saltos de línea.")
        self._processes[server_id].send_line(command)

    def restart(self, server_id: int, timeout_ms: int = 30_000) -> None:
        """Detiene el servidor y lo vuelve a iniciar cuando el proceso termina."""
        if not self.is_running(server_id):
            self.start(server_id)
            return
        self._restart_requested.add(server_id)
        self._processes[server_id].request_stop(timeout_ms)

    def pid(self, server_id: int) -> int | None:
        return self._processes[server_id].pid() if self.is_running(server_id) else None

    def shutdown(self) -> None:
        """Cierre ordenado de todos los servidores al salir de la aplicación."""
        for process in self._processes.values():
            if process.is_running():
                process.send_line("stop")
                if not process.wait_for_finish(15_000):
                    process.force_kill()

    def _create_process(self, server_id: int) -> ProcessManager:
        process = ProcessManager()
        process.output_line.connect(lambda line: self._on_line(server_id, line))
        process.finished_with_code.connect(lambda code: self._on_exit(server_id, code))
        process.error_occurred.connect(lambda message: self._on_error(server_id, message))
        return process

    def _on_line(self, server_id: int, line: str) -> None:
        self._events.publish("server.log", server_id=server_id, line=line)
        if READY_MARKER in line and self.status(server_id) == ServerStatus.STARTING:
            self._set_status(server_id, ServerStatus.ACTIVE)

    def _on_exit(self, server_id: int, exit_code: int) -> None:
        requested = server_id in self._stop_requested
        self._stop_requested.discard(server_id)
        if server_id in self._restart_requested:
            self._restart_requested.discard(server_id)
            self._set_status(server_id, ServerStatus.STOPPED)
            try:
                self.start(server_id)
            except (OSError, RuntimeError, ValueError) as error:
                log.error("No se pudo reiniciar el servidor %s: %s", server_id, error)
                self._set_status(server_id, ServerStatus.ERROR)
            return
        if requested or exit_code == 0:
            self._set_status(server_id, ServerStatus.STOPPED)
        else:
            log.error("El servidor %s terminó inesperadamente (código %s)", server_id, exit_code)
            self._set_status(server_id, ServerStatus.ERROR)

    def _on_error(self, server_id: int, message: str) -> None:
        log.error("Error del proceso del servidor %s: %s", server_id, message)
        self._set_status(server_id, ServerStatus.ERROR)

    def _set_status(self, server_id: int, status: str) -> None:
        self._status[server_id] = status
        self._events.publish("server.status_changed", server_id=server_id, status=status)
