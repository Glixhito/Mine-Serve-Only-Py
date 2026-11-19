"""Vista de jugadores: conectados, listas guardadas y acciones administrativas."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget)

from managers.player_admin import NAME_RE
from managers.player_tracker import read_name_list
from ui.widgets.components import (Badge, LockBanner, NoticeBox, PageHeader, Panel,
                                   ServerContextBar, style_button)

ACTION_LABELS = {
    "whitelist_add": ("Agregar a whitelist", "accent-outline", "plus"),
    "whitelist_remove": ("Quitar de whitelist", "default", "trash"),
    "op": ("Dar OP", "default", "shield"),
    "deop": ("Quitar OP", "default", "settings"),
    "kick": ("Expulsar", "default", "arrow"),
    "ban": ("Bloquear", "danger-subtle", "lock"),
    "pardon": ("Desbloquear", "default", "check"),
}
NEEDS_CONFIRM = {"ban", "whitelist_remove", "deop"}
LISTS = (("Whitelist", "whitelist.json"), ("Operadores", "ops.json"), ("Bloqueados", "banned-players.json"))


class PlayersView(QWidget):
    def __init__(self, core) -> None:
        super().__init__()
        self._core = core
        self._server_ids: list[int] = []

        refresh_btn = QPushButton("Actualizar")
        style_button(refresh_btn, "default", "refresh")
        refresh_btn.clicked.connect(self.refresh_all)

        header = PageHeader(
            "Jugadores",
            "Tu comunidad, siempre bajo control.",
            action_widget=refresh_btn,
        )

        self.ctx_bar = ServerContextBar(show_status=True)
        self.server_box = self.ctx_bar.combo
        self.ctx_bar.changed.connect(self.refresh_all)

        self.lock_banner = LockBanner()

        # --- Columna izquierda: Jugadores conectados ---
        self.count_badge = Badge("0 conectados", "neutral")
        left_panel = Panel("Jugadores conectados", "users", aside=self.count_badge)
        self.online_list = QListWidget()
        self.online_list.currentRowChanged.connect(self._on_pick)
        self.list_btn = QPushButton("Pedir lista al servidor")
        style_button(self.list_btn, "default", "refresh")
        self.list_btn.clicked.connect(self._request_list)

        left_panel.body_layout.addWidget(self.online_list, 1)
        left_panel.body_layout.addWidget(self.list_btn)

        # --- Columna derecha: Acciones y Listas guardadas ---
        right_col = QVBoxLayout()
        right_col.setSpacing(14)

        action_panel = Panel("Acción sobre un jugador", "shield")
        self.name = QLineEdit()
        self.name.setPlaceholderText("Nombre del jugador (3 a 16 letras, números o _)")
        self.reason = QLineEdit()
        self.reason.setPlaceholderText("Motivo (opcional, para expulsar o bloquear)")

        self.buttons: dict[str, QPushButton] = {}
        grid = QGridLayout()
        grid.setSpacing(7)
        for index, (action, (label, variant, ic)) in enumerate(ACTION_LABELS.items()):
            button = QPushButton(label)
            style_button(button, variant, ic)
            button.clicked.connect(lambda _checked=False, a=action: self._run(a))
            self.buttons[action] = button
            grid.addWidget(button, index // 2, index % 2)

        self.feedback = NoticeBox("", "green")
        self.feedback.setVisible(False)

        action_panel.body_layout.addWidget(self.name)
        action_panel.body_layout.addWidget(self.reason)
        action_panel.body_layout.addLayout(grid)
        action_panel.body_layout.addWidget(self.feedback)

        lists_panel = Panel("Listas guardadas en el servidor", "archive")
        self.tabs = QTabWidget()
        self.lists: dict[str, QListWidget] = {}
        for title, _filename in LISTS:
            widget = QListWidget()
            self.lists[title] = widget
            self.tabs.addTab(widget, title)
        self.reload_btn = QPushButton("Recargar listas")
        style_button(self.reload_btn, "default", "refresh")
        self.reload_btn.clicked.connect(self._reload_lists)

        lists_panel.body_layout.addWidget(self.tabs, 1)
        lists_panel.body_layout.addWidget(self.reload_btn)

        right_col.addWidget(action_panel)
        right_col.addWidget(lists_panel, 1)

        body = QHBoxLayout()
        body.setSpacing(16)
        body.addWidget(left_panel, 1)
        body.addLayout(right_col, 2)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(14)
        root.addWidget(header)
        root.addWidget(self.ctx_bar)
        root.addWidget(self.lock_banner)
        root.addLayout(body, 1)

        core.events.subscribe("players.changed", self._on_players_changed)
        core.events.subscribe("server.status_changed", self._on_status)
        self.refresh_all()

    def refresh(self) -> None:
        self.refresh_all()

    def refresh_all(self) -> None:
        current = self._current_id()
        self.server_box.blockSignals(True)
        self.server_box.clear()
        self._server_ids = []
        for record in self._core.servers.list_servers():
            self._server_ids.append(record.id)
            self.server_box.addItem(f"{record.name} · {record.server_type} {record.minecraft_version}")
        if current in self._server_ids:
            self.server_box.setCurrentIndex(self._server_ids.index(current))
        self.server_box.blockSignals(False)
        self._show_online()
        self._reload_lists()
        self._update_buttons()

    def _current_id(self) -> int | None:
        index = self.server_box.currentIndex()
        return self._server_ids[index] if 0 <= index < len(self._server_ids) else None

    def _record(self):
        sid = self._current_id()
        return self._core.servers.get(sid) if sid is not None else None

    def _on_players_changed(self, server_id: int) -> None:
        if server_id == self._current_id():
            self._show_online()

    def _on_status(self, server_id: int, _status: str) -> None:
        if server_id == self._current_id():
            self._show_online()
            self._update_buttons()

    def _show_online(self) -> None:
        self.online_list.clear()
        sid = self._current_id()
        if sid is None:
            self.count_badge.set_badge("0 conectados", "neutral")
            return
        names = self._core.tracker.online(sid)
        for name in names:
            self.online_list.addItem(name)
        limit = self._core.tracker.max_players(sid)
        total = f" / {limit}" if limit else ""
        self.count_badge.set_badge(f"{len(names)}{total} conectado(s)", "green" if names else "neutral", dot=bool(names))

    def _on_pick(self, row: int) -> None:
        item = self.online_list.item(row)
        if item is not None:
            self.name.setText(item.text())

    def _request_list(self) -> None:
        record = self._record()
        if record is None:
            return
        try:
            self._core.controller.send_command(record.id, "list")
        except (RuntimeError, ValueError) as error:
            QMessageBox.warning(self, "No se pudo pedir la lista", str(error))

    def _run(self, action: str) -> None:
        record = self._record()
        if record is None:
            return
        player = self.name.text().strip()
        if not NAME_RE.fullmatch(player):
            QMessageBox.warning(self, "Nombre no válido", "Usa de 3 a 16 letras, números o guion bajo.")
            return
        label = ACTION_LABELS[action][0]
        if action in NEEDS_CONFIRM:
            answer = QMessageBox.question(
                self, label, f"¿{label} a «{player}»? La acción tiene efectos inmediatos.")
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            self._core.players.run(record.id, action, player, self.reason.text())
        except (RuntimeError, ValueError, KeyError) as error:
            QMessageBox.warning(self, "No se pudo ejecutar", str(error))
            return
        self.feedback.set_text(f"Acción enviada: {label} a {player}.")
        QTimer.singleShot(1500, self._reload_lists)

    def _update_buttons(self) -> None:
        record = self._record()
        has_server = record is not None
        running = has_server and self._core.controller.is_running(record.id)
        offline = has_server and not record.online_mode
        self.ctx_bar.set_running(running, has_server)

        for action, button in self.buttons.items():
            if action in ("whitelist_add", "whitelist_remove") and offline:
                button.setEnabled(True)
            else:
                button.setEnabled(running)
        self.list_btn.setEnabled(running)

        if record is None:
            self.lock_banner.set_text("Crea un servidor en la pestaña Servidores para administrar jugadores.")
        elif not running and not offline:
            self.lock_banner.set_text("Las acciones requieren el servidor en ejecución. Las listas guardadas se ven siempre.")
        elif not running:
            self.lock_banner.set_text("El servidor está apagado: solo la whitelist está disponible. Los cambios se aplican al iniciarlo.")
        else:
            self.lock_banner.setVisible(False)

    def _reload_lists(self) -> None:
        record = self._record()
        for title, filename in LISTS:
            widget = self.lists[title]
            widget.clear()
            if record is None:
                continue
            folder = Path(record.server_path)
            if filename == "whitelist.json":
                try:
                    for entry in self._core.whitelist.read(folder):
                        widget.addItem(f"{entry['name']}  ·  {entry['uuid'] or 'sin UUID'}")
                except ValueError as error:
                    widget.addItem(f"Error: {error}")
            else:
                for name in read_name_list(folder, filename):
                    widget.addItem(name)