"""Historial de operaciones: qué se hizo, en qué servidor y con qué resultado."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ui.widgets.components import Badge, PageHeader, Panel, style_button


class HistoryView(QWidget):
    def __init__(self, core) -> None:
        super().__init__()
        self._core = core

        refresh_btn = QPushButton("Actualizar")
        style_button(refresh_btn, "default", "refresh")
        refresh_btn.clicked.connect(self.refresh)

        header = PageHeader(
            "Historial",
            "Cada cambio y cada operación, en un solo lugar.",
            action_widget=refresh_btn,
        )

        self.count_badge = Badge("0 registros", "neutral")
        panel = Panel("Registro de auditoría local", "clock", aside=self.count_badge)

        filter_row = QHBoxLayout()
        lbl = QLabel("Filtrar por servidor:")
        lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.server_box = QComboBox()
        self.server_box.setMinimumWidth(240)
        self.server_box.currentIndexChanged.connect(lambda _index: self.refresh())
        filter_row.addWidget(lbl)
        filter_row.addWidget(self.server_box)
        filter_row.addStretch()

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Fecha", "Servidor", "Operación", "Estado", "Detalle"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)

        panel.body_layout.addLayout(filter_row)
        panel.body_layout.addWidget(self.table, 1)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(14)
        root.addWidget(header)
        root.addWidget(panel, 1)

    def showEvent(self, event) -> None:
        self.refresh()
        super().showEvent(event)

    def refresh(self) -> None:
        selected = self.server_box.currentData()
        self.server_box.blockSignals(True)
        self.server_box.clear()
        self.server_box.addItem("Todos los servidores", None)
        for record in self._core.servers.list_servers():
            self.server_box.addItem(record.name, record.id)
        index = self.server_box.findData(selected) if selected is not None else 0
        self.server_box.setCurrentIndex(max(index, 0))
        self.server_box.blockSignals(False)

        rows = self._core.operations.recent(self.server_box.currentData())
        self.count_badge.set_badge(f"{len(rows)} registro(s)", "blue" if rows else "neutral")
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            when = datetime.fromisoformat(row["created_at"]).astimezone().strftime("%Y-%m-%d %H:%M:%S")
            cells = [when, row["server_name"] or "(eliminado)", row["operation_type"],
                     row["status"], row["message"] or ""]
            for column, text in enumerate(cells):
                self.table.setItem(row_index, column, QTableWidgetItem(str(text)))