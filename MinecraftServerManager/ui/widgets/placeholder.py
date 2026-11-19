"""Vista provisional para secciones de fases posteriores."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderView(QWidget):
    def __init__(self, title: str, description: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<h2>{title}</h2>"))
        layout.addWidget(QLabel(description))
        layout.addStretch()
