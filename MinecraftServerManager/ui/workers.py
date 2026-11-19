"""Ejecuta tareas bloqueantes (descargas, instalaciones, respaldos) en un hilo aparte."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)


class _Task(QRunnable):
    def __init__(self, fn: Callable[[], Any]) -> None:
        super().__init__()
        self.fn = fn
        self.signals = _Signals()
        self.setAutoDelete(False)

    def run(self) -> None:
        try:
            result = self.fn()
        except Exception as error:
            self.signals.failed.emit(str(error) or error.__class__.__name__)
        else:
            self.signals.done.emit(result)


_live: set[_Task] = set()


def run_async(fn: Callable[[], Any], on_done: Callable[[Any], None],
              on_failed: Callable[[str], None]) -> None:
    task = _Task(fn)
    _live.add(task)
    task.signals.done.connect(lambda _result: _live.discard(task))
    task.signals.failed.connect(lambda _message: _live.discard(task))
    task.signals.done.connect(on_done)
    task.signals.failed.connect(on_failed)
    QThreadPool.globalInstance().start(task)