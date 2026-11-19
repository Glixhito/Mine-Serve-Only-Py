"""Componentes reutilizables de la interfaz con el estilo del prototipo."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

from ui.widgets.icons import svg_icon, svg_pixmap


def style_button(btn: QPushButton, variant: str = "default", icon_name: str | None = None,
                 icon_color: str = "#d3dae3") -> QPushButton:
    btn.setProperty("variant", variant)
    if icon_name:
        color = "#f0f6fc" if variant == "primary" else ("#f07873" if variant == "danger-subtle" else icon_color)
        btn.setIcon(svg_icon(icon_name, size=14, color=color))
    btn.style().unpolish(btn)
    btn.style().polish(btn)
    return btn


class Badge(QLabel):
    TONES = {
        "green": ("#69c378", "rgba(46, 160, 67, 0.14)", "rgba(46, 160, 67, 0.30)"),
        "blue": ("#73b3ff", "rgba(88, 166, 255, 0.12)", "rgba(88, 166, 255, 0.25)"),
        "amber": ("#d8ad50", "rgba(210, 153, 34, 0.15)", "rgba(210, 153, 34, 0.30)"),
        "red": ("#f07873", "rgba(248, 81, 73, 0.15)", "rgba(248, 81, 73, 0.30)"),
        "neutral": ("#a0a9b5", "#242932", "#303640"),
    }

    def __init__(self, text: str = "", tone: str = "neutral", dot: bool = False) -> None:
        super().__init__()
        self._dot = dot
        self.set_badge(text, tone, dot)

    def set_badge(self, text: str, tone: str = "neutral", dot: bool | None = None) -> None:
        if dot is not None:
            self._dot = dot
        fg, bg, border = self.TONES.get(tone, self.TONES["neutral"])
        prefix = "● " if self._dot else ""
        self.setText(f"{prefix}{text}")
        self.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border: 1px solid {border};"
            "border-radius: 10px; padding: 2px 8px; font-size: 11px; font-weight: 600;"
        )


class Panel(QFrame):
    """Tarjeta contenedora con cabecera opcional y cuerpo con padding uniforme."""

    def __init__(self, title: str = "", icon_name: str | None = None,
                 aside: QWidget | None = None, hero: bool = False) -> None:
        super().__init__()
        self.setObjectName("PanelHero" if hero else "Panel")
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)

        if title:
            header = QFrame()
            header.setObjectName("PanelHeader")
            h_layout = QHBoxLayout(header)
            h_layout.setContentsMargins(16, 11, 16, 11)
            h_layout.setSpacing(8)
            if icon_name:
                ic = QLabel()
                ic.setPixmap(svg_pixmap(icon_name, 15, "#8b949e"))
                ic.setStyleSheet("background: transparent; border: none;")
                h_layout.addWidget(ic)
            lbl = QLabel(title)
            lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #f0f6fc; background: transparent; border: none;")
            h_layout.addWidget(lbl)
            h_layout.addStretch()
            if aside is not None:
                h_layout.addWidget(aside)
            self._root.addWidget(header)

        self.body = QWidget()
        self.body.setStyleSheet("background: transparent;")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(16, 16, 16, 16)
        self.body_layout.setSpacing(12)
        self._root.addWidget(self.body)


class NoticeBox(QFrame):
    STYLES = {
        "neutral": ("#a7b1bf", "#1e222b", "#303640", "info"),
        "blue": ("#8fafd5", "rgba(88, 166, 255, 0.08)", "rgba(88, 166, 255, 0.25)", "info"),
        "amber": ("#c4a363", "rgba(210, 153, 34, 0.09)", "rgba(210, 153, 34, 0.28)", "lock"),
        "red": ("#e89590", "rgba(248, 81, 73, 0.09)", "rgba(248, 81, 73, 0.28)", "info"),
        "green": ("#7bb788", "rgba(46, 160, 67, 0.09)", "rgba(46, 160, 67, 0.28)", "check"),
    }

    def __init__(self, text: str = "", tone: str = "neutral", icon_name: str | None = None) -> None:
        super().__init__()
        fg, bg, border, default_icon = self.STYLES.get(tone, self.STYLES["neutral"])
        self.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border: 1px solid {border}; border-radius: 6px; }}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 9, 12, 9)
        row.setSpacing(9)
        self._icon = QLabel()
        self._icon.setPixmap(svg_pixmap(icon_name or default_icon, 15, fg))
        self._icon.setStyleSheet("background: transparent; border: none;")
        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setStyleSheet(f"color: {fg}; font-size: 11px; background: transparent; border: none;")
        row.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(self._label, 1)

    def set_text(self, text: str) -> None:
        self._label.setText(text)
        self.setVisible(bool(text))


class LockBanner(NoticeBox):
    def __init__(self, text: str = "El servidor está en ejecución: deténlo para cambiar ajustes.") -> None:
        super().__init__(text=text, tone="amber", icon_name="lock")
        self.setVisible(False)


class PageHeader(QWidget):
    """Encabezado superior de cada vista: eyebrow, título H1, subtítulo y acción derecha."""

    def __init__(self, title: str, subtitle: str, eyebrow: str = "TU CENTRO DE CONTROL",
                 action_widget: QWidget | None = None) -> None:
        super().__init__()
        self.setStyleSheet("background: transparent;")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 8)
        row.setSpacing(16)

        col = QVBoxLayout()
        col.setSpacing(4)
        eye = QLabel(eyebrow)
        eye.setStyleSheet("font-size: 10px; font-weight: 600; color: #8fa096;")
        h1 = QLabel(title)
        h1.setStyleSheet("font-size: 22px; font-weight: 700; color: #f0f6fc;")
        sub = QLabel(subtitle)
        sub.setStyleSheet("font-size: 12px; color: #8b949e;")
        col.addWidget(eye)
        col.addWidget(h1)
        col.addWidget(sub)

        row.addLayout(col, 1)
        if action_widget is not None:
            row.addWidget(action_widget, 0, Qt.AlignmentFlag.AlignVCenter)


class ServerContextBar(QFrame):
    """Barra contextual de selección de servidor con badge de estado en tiempo real."""
    changed = Signal()

    def __init__(self, show_status: bool = True) -> None:
        super().__init__()
        self._show_status = show_status
        self.setStyleSheet(
            "QFrame { background-color: #161920; border: 1px solid #2a2f3a; border-radius: 7px; }"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(13, 8, 13, 8)
        row.setSpacing(10)

        lbl = QLabel("Servidor:")
        lbl.setStyleSheet("color: #8b949e; font-size: 11px; border: none; background: transparent;")
        self.combo = QComboBox()
        self.combo.setMinimumWidth(290)
        self.combo.currentIndexChanged.connect(lambda _idx: self.changed.emit())

        self.status_badge = Badge("Detenido", "neutral", dot=True)
        self.status_badge.setVisible(show_status)

        env_icon = QLabel()
        env_icon.setPixmap(svg_pixmap("globe", 13, "#8b949e"))
        env_icon.setStyleSheet("border: none; background: transparent;")
        env_lbl = QLabel("Entorno local")
        env_lbl.setStyleSheet("color: #8b949e; font-size: 11px; border: none; background: transparent;")

        row.addWidget(lbl)
        row.addWidget(self.combo)
        row.addWidget(self.status_badge)
        row.addStretch()
        row.addWidget(env_icon)
        row.addWidget(env_lbl)

    def set_running(self, running: bool, has_server: bool = True) -> None:
        if not self._show_status:
            return
        if not has_server:
            self.status_badge.set_badge("Sin servidor", "neutral", dot=False)
        elif running:
            self.status_badge.set_badge("En ejecución", "green", dot=True)
        else:
            self.status_badge.set_badge("Detenido", "neutral", dot=True)