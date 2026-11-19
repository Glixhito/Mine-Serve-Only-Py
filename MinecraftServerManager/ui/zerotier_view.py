"""Pestaña ZeroTier: red de cada servidor, dirección para Minecraft y autorización."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from ui.widgets.components import (Badge, NoticeBox, PageHeader, Panel,
                                   ServerContextBar, style_button)
from ui.widgets.icons import svg_pixmap
from ui.workers import run_async

STATUS_TEXT = {
    "OK": "Conectado a la red",
    "ACCESS_DENIED": "Esperando autorización: en ZeroTier Central, abre Members y marca Auth",
    "REQUESTING_CONFIGURATION": "Obteniendo configuración de la red",
    "NO_UNIDO": "No unido a la red",
}


class ZeroTierView(QWidget):
    def __init__(self, core) -> None:
        super().__init__()
        self._core = core
        self._ids: list[int] = []
        self._current_mc_address = ""

        refresh_btn = QPushButton("Actualizar")
        style_button(refresh_btn, "default", "refresh")
        refresh_btn.clicked.connect(self._show)

        header = PageHeader(
            "ZeroTier",
            "Menos configuración. Más tiempo jugando juntos.",
            action_widget=refresh_btn,
        )

        self.ctx_bar = ServerContextBar(show_status=True)
        self.server_box = self.ctx_bar.combo
        self.ctx_bar.changed.connect(self._show)

        # --- Hero Panel: Dirección para Minecraft ---
        hero = Panel(hero=True)
        hero_top = QHBoxLayout()
        hero_top.setSpacing(12)
        hero_ic = QLabel()
        hero_ic.setPixmap(svg_pixmap("network", 22, "#74c985"))
        hero_ic.setStyleSheet(
            "background-color: rgba(46, 160, 67, 0.12); border: 1px solid #36533e; "
            "border-radius: 9px; padding: 9px;"
        )
        hero_titles = QVBoxLayout()
        hero_titles.setSpacing(2)
        h_t = QLabel("Dirección de conexión para tus amigos")
        h_t.setStyleSheet("font-size: 15px; font-weight: 700; color: #f0f6fc; background: transparent;")
        h_s = QLabel("Comparte esta dirección IP y puerto para que entren desde Multijugador en Minecraft.")
        h_s.setStyleSheet("font-size: 11px; color: #819b89; background: transparent;")
        hero_titles.addWidget(h_t)
        hero_titles.addWidget(h_s)
        self.zt_badge = Badge("Sin red", "neutral", dot=True)

        hero_top.addWidget(hero_ic)
        hero_top.addLayout(hero_titles, 1)
        hero_top.addWidget(self.zt_badge)

        addr_box = QFrame()
        addr_box.setObjectName("AddressBox")
        addr_row = QHBoxLayout(addr_box)
        addr_row.setContentsMargins(16, 12, 16, 12)
        addr_col = QVBoxLayout()
        addr_col.setSpacing(4)
        addr_cap = QLabel("DIRECCIÓN PARA MINECRAFT")
        addr_cap.setStyleSheet("font-size: 9px; font-weight: 700; letter-spacing: 0.8px; color: #6d8976; border: none;")
        self.address_label = QLabel("Todavía no hay IP asignada.")
        self.address_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.address_label.setStyleSheet(
            "font-size: 17px; font-weight: 600; color: #d0e4d4; "
            "font-family: 'JetBrains Mono', monospace; border: none;"
        )
        addr_col.addWidget(addr_cap)
        addr_col.addWidget(self.address_label)

        self.copy_btn = QPushButton("Copiar IP")
        style_button(self.copy_btn, "primary", "copy")
        self.copy_btn.clicked.connect(self._copy_address)

        addr_row.addLayout(addr_col, 1)
        addr_row.addWidget(self.copy_btn)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 11px; color: #8b949e; background: transparent;")

        hero.body_layout.addLayout(hero_top)
        hero.body_layout.addWidget(addr_box)
        hero.body_layout.addWidget(self.status_label)

        # --- Dos columnas inferiores ---
        cols = QHBoxLayout()
        cols.setSpacing(16)

        # Izquierda: Red del servidor
        net_panel = Panel("Red del servidor", "globe")
        self.network_label = QLabel()
        self.network_label.setWordWrap(True)
        self.network_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.network_label.setStyleSheet("font-size: 12px; color: #c9d1d9;")

        self.network_input = QLineEdit()
        self.network_input.setPlaceholderText("ID de red de ZeroTier Central (16 caracteres)")
        use_btn = QPushButton("Usar esta red")
        style_button(use_btn, "primary", "check")
        use_btn.clicked.connect(self._use_network)
        net_row = QHBoxLayout()
        net_row.addWidget(self.network_input, 1)
        net_row.addWidget(use_btn)

        self.create_btn = QPushButton("Crear red automáticamente (requiere token)")
        style_button(self.create_btn, "default", "plus")
        self.create_btn.clicked.connect(self._create)

        net_panel.body_layout.addWidget(self.network_label)
        net_panel.body_layout.addLayout(net_row)
        net_panel.body_layout.addWidget(self.create_btn)
        net_panel.body_layout.addStretch()

        # Derecha: Autorizar amigos + Token opcional
        auth_panel = Panel("Autorizar amigos y Token API", "users")
        auth_desc = QLabel("Tu amigo se une a la red y te envía su ID de nodo (lo ve en ZeroTier One).")
        auth_desc.setWordWrap(True)
        auth_desc.setStyleSheet("font-size: 11px; color: #8b949e;")

        self.node_input = QLineEdit()
        self.node_input.setPlaceholderText("ID de nodo de tu amigo (10 caracteres)")
        self.authorize_btn = QPushButton("Autorizar")
        style_button(self.authorize_btn, "accent-outline", "check")
        self.authorize_btn.clicked.connect(self._authorize)
        auth_row = QHBoxLayout()
        auth_row.addWidget(self.node_input, 1)
        auth_row.addWidget(self.authorize_btn)

        self.auth_hint = NoticeBox("Sin token, autoriza en ZeroTier Central: Members → marca Auth.", "blue")

        token_lbl = QLabel("Token de API de ZeroTier Central (opcional)")
        token_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #aeb7c3; margin-top: 6px;")
        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.EchoMode.Password)
        self.token.setPlaceholderText("Pega tu token personal de ZeroTier Central")
        self.token.setText(core.zerotier.token())
        save_token = QPushButton("Guardar token")
        style_button(save_token, "default", "lock")
        save_token.clicked.connect(self._save_token)
        tok_row = QHBoxLayout()
        tok_row.addWidget(self.token, 1)
        tok_row.addWidget(save_token)

        auth_panel.body_layout.addWidget(auth_desc)
        auth_panel.body_layout.addLayout(auth_row)
        auth_panel.body_layout.addWidget(self.auth_hint)
        auth_panel.body_layout.addWidget(token_lbl)
        auth_panel.body_layout.addLayout(tok_row)

        cols.addWidget(net_panel, 1)
        cols.addWidget(auth_panel, 1)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(14)
        root.addWidget(header)
        root.addWidget(self.ctx_bar)
        root.addWidget(hero)
        root.addLayout(cols, 1)

        core.events.subscribe("server.status_changed", lambda _sid, _st: self._show())
        self.refresh()

    def showEvent(self, event) -> None:
        self._show()
        super().showEvent(event)

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

    def _copy_address(self) -> None:
        if self._current_mc_address:
            QGuiApplication.clipboard().setText(self._current_mc_address)
            QMessageBox.information(self, "Copiado", f"Dirección copiada:\n{self._current_mc_address}")

    def _show(self) -> None:
        sid = self._current_id()
        running = sid is not None and self._core.controller.is_running(sid)
        self.ctx_bar.set_running(running, sid is not None)
        has_token = bool(self._core.zerotier.token())
        self.auth_hint.setVisible(not has_token)
        self.authorize_btn.setEnabled(has_token and sid is not None)
        self.node_input.setEnabled(has_token and sid is not None)
        self._current_mc_address = ""
        self.copy_btn.setEnabled(False)

        if sid is None:
            self.network_label.setText("Crea un servidor en la pestaña Servidores.")
            self.address_label.setText("Sin servidor seleccionado")
            self.status_label.setText("")
            self.zt_badge.set_badge("Sin servidor", "neutral", dot=False)
            self.network_input.setEnabled(False)
            self.create_btn.setEnabled(False)
            return

        self.network_input.setEnabled(True)
        network = self._core.zerotier.network_of(sid)
        self.create_btn.setEnabled(has_token and network is None)
        if network is None:
            self.network_label.setText("Este servidor no tiene red. Pega aquí el ID de una red creada en ZeroTier Central y pulsa «Usar esta red».")
            self.address_label.setText("Red no configurada")
            self.status_label.setText("")
            self.zt_badge.set_badge("Sin red", "neutral", dot=True)
            return

        self.network_label.setText(f"ID de red (tus amigos lo usan para unirse): {network}")
        try:
            info = self._core.zerotier.address(sid)
        except RuntimeError as error:
            self.address_label.setText("No disponible")
            self.status_label.setText(str(error))
            self.zt_badge.set_badge("Error de red", "red", dot=True)
            return

        if info["minecraft"]:
            self._current_mc_address = info["minecraft"]
            self.address_label.setText(info["minecraft"])
            self.copy_btn.setEnabled(True)
        else:
            self.address_label.setText("Esperando IP… Inicia el servidor y autoriza tu PC.")

        st = info["status"]
        self.status_label.setText(f"Estado en ZeroTier: {STATUS_TEXT.get(st, st)}")
        self.zt_badge.set_badge(
            "Conectado" if st == "OK" else st,
            "green" if st == "OK" else "amber",
            dot=True,
        )

    def _use_network(self) -> None:
        sid = self._current_id()
        text = self.network_input.text().strip()
        if sid is None or not text:
            return
        try:
            self._core.zerotier.set_network(sid, text)
        except ValueError as error:
            QMessageBox.warning(self, "ID no válido", str(error))
            return
        self.network_input.clear()
        QMessageBox.information(self, "Red asignada",
                                "Inicia el servidor para unir tu PC a la red. Después autorízala "
                                "en ZeroTier Central (Members → Auth).")
        self._show()

    def _save_token(self) -> None:
        self._core.zerotier.save_token(self.token.text())
        QMessageBox.information(self, "ZeroTier", "Token guardado.")
        self._show()

    def _create(self) -> None:
        sid = self._current_id()
        if sid is None:
            return
        record = self._core.servers.get(sid)
        self.create_btn.setEnabled(False)

        def done(network) -> None:
            if network is None:
                QMessageBox.warning(self, "No se creó la red",
                                    "Revisa el token. El motivo aparece en la pestaña Historial.")
            self._show()

        def failed(error: str) -> None:
            QMessageBox.warning(self, "No se creó la red", error)
            self._show()

        run_async(lambda: self._core.zerotier.provision(record), done, failed)

    def _authorize(self) -> None:
        sid = self._current_id()
        node = self.node_input.text().strip()
        if sid is None or not node:
            return

        def done(_result) -> None:
            self.node_input.clear()
            QMessageBox.information(self, "Amigo autorizado", "Ya puede entrar a la red. Pídele que se conecte.")
            self._show()

        run_async(lambda: self._core.zerotier.authorize_friend(sid, node), done,
                  lambda error: QMessageBox.warning(self, "No se autorizó", error))