"""Diálogo de creación de servidor en 2 columnas (Core + Mods iniciales de Modrinth)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QSpinBox, QVBoxLayout)

from managers.java_manager import required_java_major
from ui.theme import GLOBAL_QSS
from ui.widgets.components import NoticeBox, style_button
from ui.workers import run_async

SEED_MAX = 64
MODS_MAX = 20
LOADERS = ["vanilla", "fabric", "forge", "neoforge"]
LEVEL_TYPES = [
    ("Normal", "minecraft:normal"),
    ("Plano", "minecraft:flat"),
    ("Biomas grandes", "minecraft:large_biomes"),
    ("Amplificado", "minecraft:amplified"),
]


def _ram_box(value: int) -> QSpinBox:
    box = QSpinBox()
    box.setRange(256, 65536)
    box.setSingleStep(256)
    box.setSuffix(" MB")
    box.setValue(value)
    return box


class CreateServerDialog(QDialog):
    def __init__(self, core, parent=None) -> None:
        super().__init__(parent)
        self._core = core
        self._token = 0
        self._mods_token = 0
        self._installs: list = []
        self._picked: dict[str, str] = {}
        self.setWindowTitle("Crear nuevo servidor")
        self.resize(880, 620)
        self.setStyleSheet(GLOBAL_QSS)
        self.params: dict = {}

        # --- Cabecera del modal ---
        header = QFrame()
        header.setStyleSheet("QFrame { background-color: #161920; border-bottom: 1px solid #2a2f3a; }")
        h_col = QVBoxLayout(header)
        h_col.setContentsMargins(22, 16, 22, 16)
        h_col.setSpacing(4)
        h_title = QLabel("Nuevo servidor de Minecraft")
        h_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #f0f6fc; border: none;")
        h_sub = QLabel("Configura el núcleo, Java, memoria y elige mods iniciales compatibles desde Modrinth.")
        h_sub.setStyleSheet("font-size: 11px; color: #85929f; border: none;")
        h_col.addWidget(h_title)
        h_col.addWidget(h_sub)

        # --- Columna izquierda: Configuración base ---
        self.name = QLineEdit()
        self.name.setPlaceholderText("Ej. Survival Amigos")
        self.version = QComboBox()
        self.version.addItem("Cargando versiones…")
        self.loader = QComboBox()
        self.loader.addItems(LOADERS)
        self.loader_version = QComboBox()
        self.loader_version.setEditable(True)
        self.loader_version.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.loader_hint = QLabel()
        self.loader_hint.setWordWrap(True)
        self.loader_hint.setStyleSheet("font-size: 10px; color: #727e8c;")
        self.java = QComboBox()
        self.java.addItem("Buscando Java…")
        self.min_ram = _ram_box(1024)
        self.max_ram = _ram_box(2048)
        self.seed = QLineEdit()
        self.seed.setMaxLength(SEED_MAX)
        self.seed.setPlaceholderText("Vacío = semilla aleatoria")
        self.level_type = QComboBox()
        for label, value in LEVEL_TYPES:
            self.level_type.addItem(label, value)
        self.online = QCheckBox("Modo premium (online-mode = true)")
        self.online.setChecked(True)
        self.risk = QCheckBox("Entiendo que el modo offline permite suplantar jugadores")
        self.risk.setVisible(False)
        self.online.toggled.connect(lambda on: self.risk.setVisible(not on))

        left_col = QVBoxLayout()
        left_col.setSpacing(10)
        step1 = QLabel("1. Configuración del núcleo")
        step1.setStyleSheet("font-size: 13px; font-weight: 600; color: #3fb950;")
        left_col.addWidget(step1)

        form = QFormLayout()
        form.setSpacing(9)
        for label, widget in (
            ("Nombre", self.name), ("Versión de Minecraft", self.version),
            ("Cargador", self.loader), ("Versión del cargador", self.loader_version),
            ("", self.loader_hint), ("Java", self.java), ("RAM mínima", self.min_ram),
            ("RAM máxima", self.max_ram), ("Semilla del mundo", self.seed),
            ("Tipo de mundo", self.level_type),
        ):
            form.addRow(label, widget)
        form.addRow(self.online)
        form.addRow(self.risk)
        left_col.addLayout(form)
        left_col.addStretch()

        # --- Columna derecha: Mods de Modrinth ---
        right_frame = QFrame()
        right_frame.setStyleSheet("QFrame { border-left: 1px solid #2a2f3a; padding-left: 16px; }")
        right_col = QVBoxLayout(right_frame)
        right_col.setContentsMargins(16, 0, 0, 0)
        right_col.setSpacing(10)

        step2 = QLabel("2. Mods iniciales · Modrinth (opcional)")
        step2.setStyleSheet("font-size: 13px; font-weight: 600; color: #3fb950; border: none;")

        self.mod_search = QLineEdit()
        self.mod_search.setPlaceholderText("Buscar mods (vacío = más descargados)")
        self.mod_search_btn = QPushButton("Buscar")
        style_button(self.mod_search_btn, "default", "search")
        self.mod_list = QListWidget()
        self.mod_hint = QLabel()
        self.mod_hint.setWordWrap(True)
        self.mod_hint.setStyleSheet("font-size: 11px; color: #8b949e; border: none;")
        self.picked_notice = NoticeBox("", "green")
        self.picked_notice.setVisible(False)

        self.mod_search_btn.clicked.connect(self._refresh_mods)
        self.mod_search.returnPressed.connect(self._refresh_mods)
        self.mod_list.itemChanged.connect(self._mod_toggled)

        search_row = QHBoxLayout()
        search_row.addWidget(self.mod_search, 1)
        search_row.addWidget(self.mod_search_btn)

        right_col.addWidget(step2)
        right_col.addLayout(search_row)
        right_col.addWidget(self.mod_list, 1)
        right_col.addWidget(self.mod_hint)
        right_col.addWidget(self.picked_notice)

        body = QHBoxLayout()
        body.setContentsMargins(22, 18, 22, 18)
        body.setSpacing(20)
        body.addLayout(left_col, 1)
        body.addWidget(right_frame, 1)

        # --- Footer del modal ---
        footer = QFrame()
        footer.setStyleSheet("QFrame { background-color: #14171d; border-top: 1px solid #2a2f3a; }")
        f_row = QHBoxLayout(footer)
        f_row.setContentsMargins(22, 12, 22, 12)
        self.message = QLabel()
        self.message.setStyleSheet("color: #f07873; font-size: 11px; border: none;")
        self.message.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("Crear servidor")
        style_button(ok_btn, "primary", "plus")
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setText("Cancelar")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        f_row.addWidget(self.message, 1)
        f_row.addWidget(buttons)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addLayout(body, 1)
        layout.addWidget(footer)

        self.version.currentTextChanged.connect(self._on_profile_changed)
        self.loader.currentTextChanged.connect(self._on_profile_changed)

        run_async(core.versions.list_release_versions, self._fill_versions, self._load_error)
        run_async(core.java.detect, self._fill_java, self._load_error)
        self._refresh_loader_versions()
        self._refresh_mods()

    def _on_profile_changed(self, _text: str = "") -> None:
        self._picked.clear()
        self._update_picked_label()
        self._filter_java()
        self._refresh_loader_versions()
        self._refresh_mods()

    def _fill_versions(self, versions: list[str]) -> None:
        self.version.clear()
        self.version.addItems(versions)

    def _fill_java(self, installs) -> None:
        self._installs = list(installs or [])
        self._filter_java()

    def _filter_java(self) -> None:
        self.java.clear()
        if not self._installs:
            self.java.addItem("No se detectó Java: instálalo y reinicia la aplicación")
            return
        version = self.version.currentText()
        if not version or version.startswith("Cargando"):
            shown = self._installs
        else:
            shown = [install for install in self._installs
                     if self._core.java.check_compatibility(install, version)[0]]
        if not shown:
            needed = required_java_major(version) or "?"
            self.java.addItem(f"Ningún Java instalado sirve para Minecraft {version}. Instala Java {needed}+.")
            return
        for install in shown:
            self.java.addItem(f"Java {install.major} — {install.path}", install.path)

    def _load_error(self, message: str) -> None:
        self.message.setText(f"No se pudo cargar la información: {message}")

    def _refresh_loader_versions(self) -> None:
        loader = self.loader.currentText()
        minecraft = self.version.currentText()
        self._token += 1
        token = self._token
        self.loader_version.clear()
        self.loader_version.setEnabled(loader != "vanilla")
        if loader == "vanilla" or not minecraft or minecraft.startswith("Cargando"):
            self.loader_hint.setText("")
            return
        self.loader_hint.setText(f"Buscando versiones de {loader} para Minecraft {minecraft}…")
        run_async(lambda: self._core.loader_catalog.versions(loader, minecraft),
                  lambda versions: self._show_loader_versions(token, loader, minecraft, versions),
                  lambda error: self._show_loader_error(token, error))

    def _show_loader_versions(self, token: int, loader: str, minecraft: str, versions: list[str]) -> None:
        if token != self._token:
            return
        self.loader_version.clear()
        if versions:
            self.loader_version.addItems(versions)
            self.loader_hint.setText(f"Versiones de {loader} para Minecraft {minecraft}. La primera es la recomendada.")
        else:
            self.loader_hint.setText(f"{loader} no tiene versiones publicadas para Minecraft {minecraft}. Escríbela manualmente.")

    def _show_loader_error(self, token: int, error: str) -> None:
        if token != self._token:
            return
        self.loader_hint.setText(f"No se pudieron cargar las versiones: {error}. Puedes escribirla a mano.")

    def _refresh_mods(self) -> None:
        loader = self.loader.currentText()
        version = self.version.currentText()
        self._mods_token += 1
        token = self._mods_token
        self.mod_list.clear()
        if loader == "vanilla":
            self.mod_search.setEnabled(False)
            self.mod_search_btn.setEnabled(False)
            self.mod_hint.setText("Con Vanilla no se pueden usar mods. Elige Fabric, Forge o NeoForge.")
            return
        self.mod_search.setEnabled(True)
        self.mod_search_btn.setEnabled(True)
        if not version or version.startswith("Cargando"):
            self.mod_hint.setText("Elige una versión de Minecraft para ver los mods compatibles.")
            return
        query = self.mod_search.text().strip()
        self.mod_hint.setText(f"Buscando mods para Minecraft {version} ({loader})…")
        run_async(lambda: self._core.modrinth.search(query, version, loader, limit=MODS_MAX),
                  lambda hits: self._show_mods(token, version, loader, hits),
                  lambda error: self._show_mods_error(token, error))

    def _show_mods(self, token: int, version: str, loader: str, hits: list[dict]) -> None:
        if token != self._mods_token:
            return
        self.mod_list.blockSignals(True)
        self.mod_list.clear()
        for hit in hits:
            item = QListWidgetItem(f"{hit.get('title', hit.get('slug', '?'))} — {hit.get('description', '')}")
            item.setData(Qt.ItemDataRole.UserRole, hit["project_id"])
            checked = hit["project_id"] in self._picked
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            self.mod_list.addItem(item)
        self.mod_list.blockSignals(False)
        if hits:
            self.mod_hint.setText(f"{len(hits)} mods compatibles con Minecraft {version} ({loader}).")
        else:
            self.mod_hint.setText(f"No hay mods para Minecraft {version} ({loader}) con esa búsqueda.")

    def _show_mods_error(self, token: int, error: str) -> None:
        if token != self._mods_token:
            return
        self.mod_hint.setText(f"No se pudieron buscar mods: {error}")

    def _mod_toggled(self, item: QListWidgetItem) -> None:
        project_id = item.data(Qt.ItemDataRole.UserRole)
        if item.checkState() == Qt.CheckState.Checked:
            self._picked[project_id] = item.text()
        else:
            self._picked.pop(project_id, None)
        self._update_picked_label()

    def _update_picked_label(self) -> None:
        if not self._picked:
            self.picked_notice.setVisible(False)
            return
        names = [name.split(" — ")[0] for name in self._picked.values()]
        self.picked_notice.set_text(f"Se instalarán ({len(names)}): {', '.join(names)}")
        self.picked_notice.setVisible(True)

    def _accept(self) -> None:
        name = self.name.text().strip()
        version = self.version.currentText()
        loader = self.loader.currentText()
        loader_version = self.loader_version.currentText().strip()
        java = self.java.currentData()
        seed = self.seed.text().strip()
        problems = []
        if not name:
            problems.append("Escribe un nombre.")
        if not version or version.startswith("Cargando"):
            problems.append("Espera a que carguen las versiones.")
        if not java:
            problems.append("Selecciona una instalación de Java compatible.")
        if loader != "vanilla" and not loader_version:
            problems.append("Elige una versión del cargador.")
        if not self.online.isChecked() and not self.risk.isChecked():
            problems.append("Confirma el riesgo del modo offline.")
        if self.min_ram.value() > self.max_ram.value():
            problems.append("La RAM mínima no puede superar la máxima.")
        if len(seed) > SEED_MAX:
            problems.append(f"La semilla admite hasta {SEED_MAX} caracteres.")
        if problems:
            self.message.setText(" ".join(problems))
            return
        self.params = {
            "name": name, "version": version, "loader": loader,
            "loader_version": loader_version, "java": java,
            "min_ram": self.min_ram.value(), "max_ram": self.max_ram.value(),
            "online": self.online.isChecked(), "seed": seed,
            "level_type": self.level_type.currentData(),
            "mods": list(self._picked.keys()),
        }
        self.accept()