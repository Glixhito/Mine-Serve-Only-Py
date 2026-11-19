"""Vista de ajustes: memoria, Java, modo de autenticación y server.properties."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QScrollArea, QSpinBox,
                               QVBoxLayout, QWidget)

from managers.config_manager import DEFAULTS
from ui.widgets.components import (LockBanner, NoticeBox, PageHeader, Panel,
                                   ServerContextBar, style_button)
from ui.workers import run_async
from utils.network import port_is_free

DIFFICULTIES = ("peaceful", "easy", "normal", "hard")
GAMEMODES = ("survival", "creative", "adventure", "spectator")
INT_KEYS = ("server-port", "max-players", "spawn-protection", "view-distance", "simulation-distance")
LABELS = {
    "motd": "MOTD (texto del listado)",
    "server-port": "Puerto",
    "max-players": "Jugadores máximos",
    "difficulty": "Dificultad",
    "gamemode": "Modo de juego",
    "pvp": "PvP",
    "white-list": "Whitelist",
    "view-distance": "Distancia de vista",
    "simulation-distance": "Distancia de simulación",
    "spawn-protection": "Protección del spawn",
    "level-name": "Nombre del mundo",
}


def _spin(low: int, high: int) -> QSpinBox:
    box = QSpinBox()
    box.setRange(low, high)
    return box


def _as_int(value: str | None, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _set_combo(combo: QComboBox, text: str) -> None:
    index = combo.findText(text)
    combo.setCurrentIndex(index if index >= 0 else 0)


class SettingsView(QWidget):
    def __init__(self, core) -> None:
        super().__init__()
        self._core = core
        self._server_ids: list[int] = []
        self._installs: list = []
        self._loaded: dict[str, str] = {}

        refresh_btn = QPushButton("Actualizar")
        style_button(refresh_btn, "default", "refresh")
        refresh_btn.clicked.connect(self.refresh)

        header = PageHeader(
            "Ajustes",
            "Afina cada detalle de tu servidor.",
            action_widget=refresh_btn,
        )

        self.ctx_bar = ServerContextBar(show_status=True)
        self.server_box = self.ctx_bar.combo
        self.ctx_bar.changed.connect(self._load)

        self.lock_banner = LockBanner("El servidor está en ejecución: deténlo para cambiar ajustes.")
        self.status_box = NoticeBox("", "green")
        self.status_box.setVisible(False)

        # --- Panel 1: Memoria y Java ---
        runtime_panel = Panel("Memoria y entorno Java", "memory")
        self.min_ram = _spin(256, 65536)
        self.max_ram = _spin(256, 65536)
        for box in (self.min_ram, self.max_ram):
            box.setSingleStep(256)
            box.setSuffix(" MB")
        self.java = QComboBox()
        self.java.currentIndexChanged.connect(lambda _index: self._update_java_hint())
        self.java_hint = QLabel()
        self.java_hint.setWordWrap(True)
        self.java_hint.setStyleSheet("font-size: 11px; color: #8b949e;")
        self.detect_btn = QPushButton("Buscar Java otra vez")
        style_button(self.detect_btn, "default", "search")
        self.detect_btn.clicked.connect(self._detect_java)
        self.runtime_btn = QPushButton("Guardar memoria y Java")
        style_button(self.runtime_btn, "primary", "check")
        self.runtime_btn.clicked.connect(self._save_runtime)

        runtime_form = QFormLayout()
        runtime_form.addRow("RAM mínima", self.min_ram)
        runtime_form.addRow("RAM máxima", self.max_ram)
        runtime_form.addRow("Instalación de Java", self.java)
        runtime_buttons = QHBoxLayout()
        runtime_buttons.addWidget(self.detect_btn)
        runtime_buttons.addStretch()
        runtime_buttons.addWidget(self.runtime_btn)
        runtime_panel.body_layout.addLayout(runtime_form)
        runtime_panel.body_layout.addWidget(self.java_hint)
        runtime_panel.body_layout.addLayout(runtime_buttons)

        # --- Panel 2: Autenticación ---
        auth_panel = Panel("Autenticación de jugadores", "shield")
        self.online = QCheckBox("Modo premium (online-mode = true)")
        self.online.toggled.connect(lambda on: self.risk.setVisible(not on))
        self.risk = QCheckBox("Entiendo que el modo offline permite suplantar jugadores")
        self.risk.setVisible(False)
        self.auth_btn = QPushButton("Aplicar modo de autenticación")
        style_button(self.auth_btn, "default", "lock")
        self.auth_btn.clicked.connect(self._save_auth)

        auth_panel.body_layout.addWidget(self.online)
        auth_panel.body_layout.addWidget(self.risk)
        auth_panel.body_layout.addWidget(self.auth_btn)

        # --- Panel 3: server.properties ---
        props_panel = Panel("Propiedades del servidor (server.properties)", "settings")
        self.props = {
            "motd": QLineEdit(),
            "server-port": _spin(1, 65535),
            "max-players": _spin(1, 1000),
            "difficulty": QComboBox(),
            "gamemode": QComboBox(),
            "pvp": QCheckBox(),
            "white-list": QCheckBox(),
            "view-distance": _spin(2, 32),
            "simulation-distance": _spin(3, 32),
            "spawn-protection": _spin(0, 1000),
            "level-name": QLineEdit(),
        }
        self.props["difficulty"].addItems(DIFFICULTIES)
        self.props["gamemode"].addItems(GAMEMODES)
        self.port_label = QLabel()
        self.port_label.setStyleSheet("font-size: 11px; color: #8b949e;")
        self.port_btn = QPushButton("Comprobar puerto")
        style_button(self.port_btn, "default", "network")
        self.port_btn.clicked.connect(self._check_port)
        self.props_reload_btn = QPushButton("Recargar")
        style_button(self.props_reload_btn, "ghost", "refresh")
        self.props_reload_btn.clicked.connect(self._load)
        self.props_save_btn = QPushButton("Guardar propiedades")
        style_button(self.props_save_btn, "primary", "check")
        self.props_save_btn.clicked.connect(self._save_properties)

        props_form = QFormLayout()
        for key, widget in self.props.items():
            props_form.addRow(LABELS[key], widget)
        props_buttons = QHBoxLayout()
        props_buttons.addWidget(self.port_btn)
        props_buttons.addWidget(self.port_label, 1)
        props_buttons.addWidget(self.props_reload_btn)
        props_buttons.addWidget(self.props_save_btn)
        props_panel.body_layout.addLayout(props_form)
        props_panel.body_layout.addLayout(props_buttons)

        body = QWidget()
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, 8, 0)
        column.setSpacing(14)
        column.addWidget(runtime_panel)
        column.addWidget(auth_panel)
        column.addWidget(props_panel)
        column.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(14)
        root.addWidget(header)
        root.addWidget(self.ctx_bar)
        root.addWidget(self.lock_banner)
        root.addWidget(self.status_box)
        root.addWidget(scroll, 1)

        core.events.subscribe("server.status_changed", lambda _sid, _st: self._update_lock())
        self.refresh()

    def refresh(self) -> None:
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
        self._load()
        self._detect_java()

    def _current_id(self) -> int | None:
        index = self.server_box.currentIndex()
        return self._server_ids[index] if 0 <= index < len(self._server_ids) else None

    def _record(self):
        sid = self._current_id()
        return self._core.servers.get(sid) if sid is not None else None

    def _is_running(self, record) -> bool:
        return self._core.controller.is_running(record.id)

    def _load(self) -> None:
        record = self._record()
        if record is None:
            self.status_box.set_text("Crea un servidor en la pestaña Servidores para ajustarlo.")
            self._update_lock()
            return
        self.min_ram.setValue(record.min_ram)
        self.max_ram.setValue(record.max_ram)
        self.online.setChecked(record.online_mode)
        self.risk.setChecked(False)
        self._loaded = {**DEFAULTS, **self._core.config.read(Path(record.server_path))}
        self._fill_props(self._loaded)
        self._select_java(record.java_path)
        self.status_box.setVisible(False)
        self._update_lock()

    def _update_lock(self) -> None:
        record = self._record()
        has_server = record is not None
        running = has_server and self._is_running(record)
        self.ctx_bar.set_running(running, has_server)
        self.lock_banner.setVisible(running)
        editable = has_server and not running
        for widget in (self.min_ram, self.max_ram, self.java, self.runtime_btn, self.online,
                       self.auth_btn, self.props_save_btn, self.props_reload_btn, self.port_btn,
                       *self.props.values()):
            widget.setEnabled(editable)
        self.risk.setEnabled(editable)

    def _detect_java(self) -> None:
        self.java.blockSignals(True)
        self.java.clear()
        self.java.addItem("Buscando Java…")
        self.java.blockSignals(False)
        self.detect_btn.setEnabled(False)
        run_async(self._core.java.detect, self._fill_java, self._java_failed)

    def _fill_java(self, installs) -> None:
        self._installs = installs
        self.detect_btn.setEnabled(True)
        self.java.blockSignals(True)
        self.java.clear()
        if not installs:
            self.java.addItem("No se detectó Java: instálalo y busca otra vez")
        for install in installs:
            self.java.addItem(f"Java {install.major} — {install.path}", install.path)
        self.java.blockSignals(False)
        record = self._record()
        self._select_java(record.java_path if record else None)

    def _java_failed(self, message: str) -> None:
        self.detect_btn.setEnabled(True)
        self.java_hint.setText(f"No se pudo buscar Java: {message}")

    def _select_java(self, path: str | None) -> None:
        for index in range(self.java.count()):
            if self.java.itemData(index) == path:
                self.java.setCurrentIndex(index)
                return
        self._update_java_hint()

    def _update_java_hint(self) -> None:
        record = self._record()
        path = self.java.currentData()
        install = next((i for i in self._installs if i.path == path), None)
        if record is None or install is None:
            self.java_hint.setText("Sin Java válido seleccionado.")
            return
        ok, message = self._core.java.check_compatibility(install, record.minecraft_version)
        self.java_hint.setText(f"Compatible con Minecraft {record.minecraft_version}." if ok else message)

    def _save_runtime(self) -> None:
        record = self._record()
        if record is None or self._is_running(record):
            return
        path = self.java.currentData()
        install = next((i for i in self._installs if i.path == path), None)
        if install is None:
            self.status_box.set_text("Selecciona una instalación de Java válida.")
            return
        ok, message = self._core.java.check_compatibility(install, record.minecraft_version)
        if not ok:
            QMessageBox.warning(self, "Java no compatible", message)
            return
        try:
            self._core.servers.update_runtime(record.id, java_path=path,
                                              min_ram=self.min_ram.value(), max_ram=self.max_ram.value())
        except ValueError as error:
            QMessageBox.warning(self, "Memoria no válida", str(error))
            return
        self.status_box.set_text("Memoria y Java guardadas. Se aplican al iniciar el servidor.")

    def _save_auth(self) -> None:
        record = self._record()
        if record is None or self._is_running(record):
            return
        online = self.online.isChecked()
        risk = self.risk.isChecked()
        if not online and not risk:
            self.status_box.set_text("Confirma el riesgo del modo offline antes de aplicarlo.")
            return
        try:
            self._core.servers.set_online_mode(record.id, online, acknowledged_risk=risk)
        except (PermissionError, OSError, KeyError) as error:
            QMessageBox.warning(self, "No se pudo cambiar", str(error))
            return
        self._loaded["online-mode"] = "true" if online else "false"
        self.risk.setChecked(False)
        self.status_box.set_text("Modo de autenticación aplicado.")

    def _fill_props(self, values: dict[str, str]) -> None:
        props = self.props
        props["motd"].setText(values.get("motd", ""))
        props["level-name"].setText(values.get("level-name", "world"))
        _set_combo(props["difficulty"], values.get("difficulty", "easy"))
        _set_combo(props["gamemode"], values.get("gamemode", "survival"))
        props["pvp"].setChecked(values.get("pvp", "true") == "true")
        props["white-list"].setChecked(values.get("white-list", "true") == "true")
        for key in INT_KEYS:
            props[key].setValue(_as_int(values.get(key), int(DEFAULTS[key])))

    def _collect_props(self) -> dict[str, str]:
        p = self.props
        return {
            "motd": p["motd"].text().strip(),
            "level-name": p["level-name"].text().strip(),
            "difficulty": p["difficulty"].currentText(),
            "gamemode": p["gamemode"].currentText(),
            "pvp": "true" if p["pvp"].isChecked() else "false",
            "white-list": "true" if p["white-list"].isChecked() else "false",
            "server-port": str(p["server-port"].value()),
            "max-players": str(p["max-players"].value()),
            "spawn-protection": str(p["spawn-protection"].value()),
            "view-distance": str(p["view-distance"].value()),
            "simulation-distance": str(p["simulation-distance"].value()),
        }

    def _save_properties(self) -> None:
        record = self._record()
        if record is None or self._is_running(record):
            return
        collected = self._collect_props()
        changes = {key: value for key, value in collected.items() if value != self._loaded.get(key)}
        if not changes:
            self.status_box.set_text("No hay cambios que guardar.")
            return
        if "level-name" in changes:
            answer = QMessageBox.question(
                self, "Nombre del mundo",
                "Cambiar el nombre del mundo hace que el servidor cree un mundo nuevo al iniciar. "
                "El mundo anterior no se borra. ¿Continuar?")
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            self._core.config.write(Path(record.server_path), changes)
        except ValueError as error:
            QMessageBox.warning(self, "Valor no válido", str(error))
            return
        self._loaded.update(changes)
        self.status_box.set_text(f"Propiedades guardadas ({len(changes)} cambio(s)). Se aplican al iniciar el servidor.")

    def _check_port(self) -> None:
        port = self.props["server-port"].value()
        free = port_is_free(port)
        self.port_label.setText(f"Puerto {port}: libre" if free else f"Puerto {port}: ocupado por otro programa")