"""Ejecuta el servidor como proceso independiente con QProcess, sin bloquear la interfaz."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal


class ProcessManager(QObject):
    output_line = Signal(str)         # cada línea de consola
    finished_with_code = Signal(int)  # código de salida al terminar
    error_occurred = Signal(str)      # fallo al iniciar o durante la ejecución

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_output)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(
            lambda _error: self.error_occurred.emit(self._process.errorString())
        )
        self._kill_timer = QTimer(self)
        self._kill_timer.setSingleShot(True)
        self._kill_timer.timeout.connect(self.force_kill)
        self._buffer = ""

    def is_running(self) -> bool:
        return self._process.state() != QProcess.ProcessState.NotRunning

    def start(self, program: str, args: list[str], cwd: Path) -> None:
        """Lanza el proceso con lista de argumentos (sin shell, sin concatenar texto)."""
        if self.is_running():
            raise RuntimeError("El proceso ya está en ejecución.")
        self._buffer = ""
        self._process.setWorkingDirectory(str(cwd))
        self._process.start(program, args)

    def send_line(self, text: str) -> None:
        if self.is_running():
            self._process.write((text + "\n").encode("utf-8"))

    def request_stop(self, timeout_ms: int = 30_000) -> None:
        """Pide parada ordenada con 'stop' y fuerza el cierre si no termina a tiempo."""
        if self.is_running():
            self.send_line("stop")
            self._kill_timer.start(timeout_ms)

    def wait_for_finish(self, timeout_ms: int) -> bool:
        """Espera bloqueante; úsese solo al cerrar la aplicación."""
        return self._process.waitForFinished(timeout_ms)

    def pid(self) -> int:
        """PID del proceso Java; lo usa el monitor de recursos."""
        return int(self._process.processId())

    def force_kill(self) -> None:
        if self.is_running():
            self._process.kill()

    def _on_output(self) -> None:
        data = self._process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        *lines, self._buffer = (self._buffer + data).split("\n")
        for line in lines:
            self.output_line.emit(line.rstrip("\r"))

    def _on_finished(self, exit_code: int, _status) -> None:
        self._kill_timer.stop()
        if self._buffer:
            self.output_line.emit(self._buffer)
            self._buffer = ""
        self.finished_with_code.emit(exit_code)
