"""Pestaña Rendimiento: aplica el preset Óptimo a un servidor detenido, con respaldo previo."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QHeaderView, QLabel, QMessageBox, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from managers.presets import OPTIMAL_PROPERTIES, OPTIMAL_RAM_MB
from ui.widgets.components import (Badge, LockBanner, NoticeBox, PageHeader, Panel,
                                   ServerContextBar, style_button)
from ui.workers import run_async


class PresetsView(QWidget):
    def __init__(self, core) -> None:
        super().__init__()
        self._core = core
        self._ids: list[int] = []
        self._busy = False

        refresh_btn = QPushButton("Actualizar")
        style_button(refresh_btn, "default", "refresh")
        refresh_btn.clicked.connect(self.refresh)

        header = PageHeader(
            "Rendimiento",
            "Un mundo más fluido empieza con la configuración correcta.",
            action_widget=refresh_btn,
        )

        self.ctx_bar = ServerContextBar(show_status=True)
        self.server_box = self.ctx_bar.combo
        self.ctx_bar.changed.connect(self._show)

        self.lock_banner = LockBanner("El servidor está en ejecución: deténlo para aplicar el preset.")

        panel = Panel("Preset Óptimo recomendado", "zap",
                      aside=Badge("RESPALDO PREVIO INCLUIDO", "green"))
        intro = QLabel(
            f"Ajusta automáticamente la memoria a {OPTIMAL_RAM_MB} MB y equilibra la distancia de renderizado "
            "y simulación para reducir lag en partidas multijugador."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("font-size: 12px; color: #a0a8b4;")

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Parámetro", "Valor actual", "Preset Óptimo"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)

        self.status_box = NoticeBox("Antes de aplicarlo se guardará un respaldo previo del servidor.", "blue")

        self.apply_btn = QPushButton("Aplicar preset Óptimo")
        style_button(self.apply_btn, "primary", "zap")
        self.apply_btn.clicked.connect(self._apply)

        panel.body_layout.addWidget(intro)
        panel.body_layout.addWidget(self.table, 1)
        panel.body_layout.addWidget(self.status_box)
        panel.body_layout.addWidget(self.apply_btn)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(14)
        root.addWidget(header)
        root.addWidget(self.ctx_bar)
        root.addWidget(self.lock_banner)
        root.addWidget(panel, 1)

        core.events.subscribe("server.status_changed", lambda _sid, _st: self._show())
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

    def _show(self) -> None:
        sid = self._current_id()
        running = sid is not None and self._core.controller.is_running(sid)
        self.ctx_bar.set_running(running, sid is not None)
        self.lock_banner.setVisible(running)

        if sid is None:
            self.table.setRowCount(0)
            self.apply_btn.setEnabled(False)
            return

        record = self._core.servers.get(sid)
        props = self._core.config.read(Path(record.server_path))
        comparisons = [
            ("RAM mínima / máxima", f"{record.min_ram} / {record.max_ram} MB", f"{OPTIMAL_RAM_MB} / {OPTIMAL_RAM_MB} MB"),
        ]
        for key, opt_val in OPTIMAL_PROPERTIES.items():
            comparisons.append((key, str(props.get(key, "—")), str(opt_val)))

        self.table.setRowCount(len(comparisons))
        for r, (param, cur_v, opt_v) in enumerate(comparisons):
            self.table.setItem(r, 0, QTableWidgetItem(param))
            self.table.setItem(r, 1, QTableWidgetItem(cur_v))
            self.table.setItem(r, 2, QTableWidgetItem(opt_v))

        self.apply_btn.setEnabled(not running and not self._busy)

    def _apply(self) -> None:
        sid = self._current_id()
        if sid is None or self._busy:
            return
        if self._core.controller.is_running(sid):
            QMessageBox.warning(self, "Servidor en ejecución", "Detén el servidor antes de aplicar el preset.")
            return
        changes = "\n".join(f"• {line}" for line in self._core.presets.describe())
        answer = QMessageBox.question(
            self, "Aplicar preset Óptimo",
            f"Se aplicará:\n{changes}\n\nAntes se guardará un respaldo previo del servidor. ¿Continuar?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._busy = True
        self.status_box.set_text("Creando respaldo previo y aplicando el preset…")
        self._show()

        def done(backup) -> None:
            self._busy = False
            self.status_box.set_text(f"Preset aplicado. Respaldo previo guardado: {backup.name}.")
            self._show()

        def failed(error: str) -> None:
            self._busy = False
            self._core.operations.add(sid, "preset óptimo", "fallido", error)
            self.status_box.set_text(f"No se aplicó el preset: {error}")
            QMessageBox.warning(self, "No se aplicó el preset", error)
            self._show()

        run_async(lambda: self._core.presets.apply_optimal(sid, running=False), done, failed)