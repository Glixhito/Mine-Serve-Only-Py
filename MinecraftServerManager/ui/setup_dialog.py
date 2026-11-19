"""Asistente de primer arranque: instala Java 25 y ZeroTier si faltan, sin salir de la app."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from managers.setup_check import all_ok, evaluate
from ui.theme import GLOBAL_QSS
from ui.widgets.components import NoticeBox, style_button
from ui.widgets.icons import svg_pixmap
from ui.workers import run_async


class SetupDialog(QDialog):
    def __init__(self, core, java, zerotier, parent=None) -> None:
        super().__init__(parent)
        self._core, self._java, self._zerotier = core, java, zerotier
        self.setWindowTitle("Preparar Minecraft Server Manager")
        self.setMinimumWidth(520)
        self.setStyleSheet(GLOBAL_QSS)

        header = QFrame()
        header.setStyleSheet("QFrame { background-color: #161920; border-bottom: 1px solid #2a2f3a; }")
        h_col = QVBoxLayout(header)
        h_col.setContentsMargins(22, 16, 22, 16)
        h_title = QLabel("Todo listo para empezar")
        h_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #f0f6fc; border: none;")
        h_sub = QLabel("Comprobemos los componentes necesarios para dar vida a tus mundos.")
        h_sub.setStyleSheet("font-size: 11px; color: #8b949e; border: none;")
        h_col.addWidget(h_title)
        h_col.addWidget(h_sub)

        body = QVBoxLayout()
        body.setContentsMargins(22, 18, 22, 18)
        body.setSpacing(12)

        self._java_label, self._zt_label = QLabel(), QLabel()
        self._java_label.setWordWrap(True)
        self._zt_label.setWordWrap(True)
        self._java_btn = QPushButton("Instalar Java 25")
        style_button(self._java_btn, "primary", "download")
        self._java_btn.clicked.connect(self._install_java)
        self._zt_btn = QPushButton("Instalar ZeroTier")
        style_button(self._zt_btn, "default", "download")
        self._zt_btn.clicked.connect(self._install_zerotier)

        for icon_name, label, button in (
            ("cube", self._java_label, self._java_btn),
            ("network", self._zt_label, self._zt_btn),
        ):
            card = QFrame()
            card.setObjectName("Panel")
            row = QHBoxLayout(card)
            row.setContentsMargins(14, 12, 14, 12)
            row.setSpacing(12)
            ic = QLabel()
            ic.setPixmap(svg_pixmap(icon_name, 20, "#3fb950"))
            ic.setStyleSheet("border: none; background: transparent;")
            label.setStyleSheet("border: none; background: transparent; font-size: 12px;")
            row.addWidget(ic)
            row.addWidget(label, 1)
            row.addWidget(button)
            body.addWidget(card)

        self._note = NoticeBox("", "blue")
        self._note.setVisible(False)  # oculto hasta que haya un mensaje que mostrar
        body.addWidget(self._note)

        footer = QFrame()
        footer.setStyleSheet("QFrame { background-color: #14171d; border-top: 1px solid #2a2f3a; }")
        f_row = QHBoxLayout(footer)
        f_row.setContentsMargins(22, 12, 22, 12)
        f_row.addStretch()
        self._continue_btn = QPushButton("Continuar")
        style_button(self._continue_btn, "primary", "arrow")
        self._continue_btn.clicked.connect(self.accept)
        f_row.addWidget(self._continue_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addLayout(body, 1)
        layout.addWidget(footer)
        self.refresh()

    def _java_ready(self) -> bool:
        return self._java.installed_java() is not None or any(i.major >= 25 for i in self._core.java.detect())

    def refresh(self) -> None:
        java_ok, zerotier_ok = self._java_ready(), self._zerotier.is_installed()
        java_req, zt_req = evaluate(java_ok, zerotier_ok)
        self._java_label.setText(f"<b>{java_req.title}</b><br><span style='color:#8b949e;'>{java_req.detail}</span>")
        self._zt_label.setText(f"<b>{zt_req.title}</b><br><span style='color:#8b949e;'>{zt_req.detail}</span>")
        self._java_btn.setEnabled(not java_ok)
        self._zt_btn.setEnabled(not zerotier_ok)
        self._continue_btn.setEnabled(all_ok([java_req, zt_req]))

    def _busy(self, message: str) -> None:
        for widget in (self._java_btn, self._zt_btn, self._continue_btn):
            widget.setEnabled(False)
        self._note.set_text(message)

    def _install_java(self) -> None:
        self._busy("Descargando Java 25 desde Adoptium…")
        run_async(self._java.install, self._finished, self._failed)

    def _install_zerotier(self) -> None:
        self._busy("Descargando ZeroTier. Windows pedirá permiso de administrador…")
        run_async(self._zerotier.install, self._finished, self._failed)

    def _finished(self, _result=None) -> None:
        self._note.set_text("Instalación terminada.")
        self.refresh()

    def _failed(self, message: str) -> None:
        self._note.set_text(f"No se pudo completar: {message}")
        self.refresh()