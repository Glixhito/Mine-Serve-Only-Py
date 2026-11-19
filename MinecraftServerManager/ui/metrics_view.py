"""Métricas del servidor: gráficas de CPU y RAM de los últimos minutos."""
from __future__ import annotations

from collections import deque

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from ui.widgets.components import Badge, PageHeader, Panel, ServerContextBar, style_button
from ui.widgets.sparkline import Sparkline

SAMPLE_MS = 2000
MAX_SAMPLES = 300


class MetricsView(QWidget):
    def __init__(self, core) -> None:
        super().__init__()
        self._core = core
        self._ids: list[int] = []
        self._samples: dict[int, deque[dict]] = {}

        refresh_btn = QPushButton("Actualizar")
        style_button(refresh_btn, "default", "refresh")
        refresh_btn.clicked.connect(self.refresh)

        header = PageHeader(
            "Métricas",
            "Cada recurso cuenta. Conoce el estado de tu servidor.",
            action_widget=refresh_btn,
        )

        self.ctx_bar = ServerContextBar(show_status=True)
        self.server_box = self.ctx_bar.combo
        self.ctx_bar.changed.connect(self._show)

        self.summary_badge = Badge("Sin muestras", "neutral")
        cpu_panel = Panel("Rendimiento del procesador y memoria", "activity", aside=self.summary_badge)

        self.cpu_chart = Sparkline("CPU del equipo (%)", fixed_max=100, accent="#3fb950", unit=" %")
        self.ram_chart = Sparkline("RAM del proceso (MB)", accent="#58a6ff", unit=" MB")

        cpu_panel.body_layout.addWidget(self.cpu_chart, 1)
        cpu_panel.body_layout.addWidget(self.ram_chart, 1)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(14)
        root.addWidget(header)
        root.addWidget(self.ctx_bar)
        root.addWidget(cpu_panel, 1)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._sample)
        self._timer.start(SAMPLE_MS)
        self.refresh()

    def refresh(self) -> None:
        current = self._current_id()
        self.server_box.blockSignals(True)
        self.server_box.clear()
        self._ids = []
        for record in self._core.servers.list_servers():
            self._ids.append(record.id)
            self.server_box.addItem(record.name)
        if current in self._ids:
            self.server_box.setCurrentIndex(self._ids.index(current))
        self.server_box.blockSignals(False)
        self._show()

    def _current_id(self) -> int | None:
        index = self.server_box.currentIndex()
        return self._ids[index] if 0 <= index < len(self._ids) else None

    def _sample(self) -> None:
        sid = self._current_id()
        if sid is None:
            return
        snapshot = self._core.monitor.snapshot(self._core.controller.pid(sid))
        if snapshot:
            self._samples.setdefault(sid, deque(maxlen=MAX_SAMPLES)).append(snapshot)
        self._show()

    def _show(self) -> None:
        sid = self._current_id()
        running = sid is not None and self._core.controller.is_running(sid)
        self.ctx_bar.set_running(running, sid is not None)
        samples = list(self._samples.get(sid, ())) if sid is not None else []
        if not samples:
            self.summary_badge.set_badge("Sin datos en vivo", "neutral")
            self.cpu_chart.set_values([])
            self.ram_chart.set_values([])
            return
        latest = samples[-1]
        self.summary_badge.set_badge(
            f"CPU {latest['cpu_pct']} % · RAM {latest['ram_mb']} MB · {latest['uptime_s']} s",
            "green" if running else "neutral",
            dot=running,
        )
        self.cpu_chart.set_values([sample["cpu_pct"] for sample in samples])
        self.ram_chart.set_values([sample["ram_mb"] for sample in samples])