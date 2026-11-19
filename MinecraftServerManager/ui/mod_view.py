"""Vista de mods: lado de cada mod, activar, eliminar, buscar e instalar con advertencias de cliente."""
from __future__ import annotations

from pathlib import Path

import psutil
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from managers.mod_doctor import ModDoctor
from managers.mod_manager import ModError
from managers.mod_sides import blocks_server, side_label
from managers.resource_advisor import assess
from managers.server_diagnostics import diagnose
from ui.widgets.components import (Badge, LockBanner, NoticeBox, PageHeader, Panel,
                                   ServerContextBar, style_button)
from ui.workers import run_async


def _table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    table.verticalHeader().setVisible(False)
    return table


def _fill(table: QTableWidget, rows: list[list[str]]) -> None:
    table.setRowCount(len(rows))
    for row_index, cells in enumerate(rows):
        for column, text in enumerate(cells):
            table.setItem(row_index, column, QTableWidgetItem(text))


class ModView(QWidget):
    def __init__(self, core) -> None:
        super().__init__()
        self._core = core
        self._server_ids: list[int] = []
        self._mods: list = []
        self._missing_ids: list[str] = []
        self._hits: list[dict] = []
        self._busy = False
        self._token = 0
        self._side_cache: dict[str, str] = {}

        refresh_btn = QPushButton("Actualizar")
        style_button(refresh_btn, "default", "refresh")
        refresh_btn.clicked.connect(self.refresh)

        header = PageHeader(
            "Mods",
            "Personaliza tu mundo con lo mejor de la comunidad.",
            action_widget=refresh_btn,
        )

        self.ctx_bar = ServerContextBar(show_status=True)
        self.server_box = self.ctx_bar.combo
        self.ctx_bar.changed.connect(self._load_mods)

        self.lock_banner = LockBanner("El servidor está en ejecución: deténlo para activar, desactivar, eliminar o instalar mods.")
        self.note_box = NoticeBox("", "blue")
        self.note_box.setVisible(False)

        # --- Panel izquierdo: Mods instalados ---
        self.installed_count = Badge("0", "neutral")
        left_panel = Panel("Mods instalados", "mods", aside=self.installed_count)

        self.mod_table = _table(["Nombre", "Versión", "Cargador", "Estado", "Lado"])
        self.mod_table.itemSelectionChanged.connect(self._update_buttons)
        self.toggle_btn = QPushButton("Activar / desactivar")
        style_button(self.toggle_btn, "default", "refresh")
        self.toggle_btn.clicked.connect(self._toggle)
        self.delete_btn = QPushButton("Eliminar mod")
        style_button(self.delete_btn, "danger-subtle", "trash")
        self.delete_btn.clicked.connect(self._delete)

        self.deps_btn = QPushButton("Arreglar mods automáticamente")
        style_button(self.deps_btn, "accent-outline", "zap")
        self.deps_btn.clicked.connect(self._auto_fix)
        self.diag_btn = QPushButton("Diagnosticar servidor")
        style_button(self.diag_btn, "default", "activity")
        self.diag_btn.clicked.connect(self._diagnose)
        self.folder_btn = QPushButton("Abrir carpeta de mods")
        style_button(self.folder_btn, "ghost", "folder")
        self.folder_btn.clicked.connect(self._open_mods_folder)

        self.warnings_box = NoticeBox("Sin advertencias.", "neutral")

        local_buttons = QHBoxLayout()
        local_buttons.addWidget(self.toggle_btn)
        local_buttons.addWidget(self.delete_btn)

        util_buttons = QHBoxLayout()
        util_buttons.addWidget(self.deps_btn)
        util_buttons.addWidget(self.diag_btn)

        left_panel.body_layout.addWidget(self.mod_table, 1)
        left_panel.body_layout.addLayout(local_buttons)
        left_panel.body_layout.addLayout(util_buttons)
        left_panel.body_layout.addWidget(self.folder_btn)
        left_panel.body_layout.addWidget(self.warnings_box)

        # --- Panel derecho: Descubre en Modrinth ---
        right_panel = Panel("Descubre en Modrinth", "search", aside=Badge("API EN VIVO", "green"))
        self.query = QLineEdit()
        self.query.setPlaceholderText("Buscar mods en Modrinth…")
        self.query.returnPressed.connect(self._search)
        self.search_btn = QPushButton("Buscar")
        style_button(self.search_btn, "primary", "search")
        self.search_btn.clicked.connect(self._search)

        self.result_table = _table(["Nombre", "Descripción", "Lado"])
        self.result_table.itemSelectionChanged.connect(self._update_buttons)
        self.install_btn = QPushButton("Instalar seleccionado")
        style_button(self.install_btn, "primary", "download")
        self.install_btn.clicked.connect(self._install)

        search_row = QHBoxLayout()
        search_row.addWidget(self.query, 1)
        search_row.addWidget(self.search_btn)

        right_panel.body_layout.addLayout(search_row)
        right_panel.body_layout.addWidget(self.result_table, 1)
        right_panel.body_layout.addWidget(self.install_btn)

        body = QHBoxLayout()
        body.setSpacing(16)
        body.addWidget(left_panel, 1)
        body.addWidget(right_panel, 1)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(14)
        root.addWidget(header)
        root.addWidget(self.ctx_bar)
        root.addWidget(self.lock_banner)
        root.addWidget(self.note_box)
        root.addLayout(body, 1)

        core.events.subscribe("server.status_changed", lambda _sid, _st: self._update_buttons())
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
        self._load_mods()

    def _current_id(self) -> int | None:
        index = self.server_box.currentIndex()
        return self._server_ids[index] if 0 <= index < len(self._server_ids) else None

    def _record(self):
        sid = self._current_id()
        return self._core.servers.get(sid) if sid is not None else None

    def _selected_mod(self):
        row = self.mod_table.currentRow()
        return self._mods[row] if 0 <= row < len(self._mods) else None

    def _load_mods(self) -> None:
        self._token += 1
        token = self._token
        self.mod_table.setRowCount(0)
        self._mods = []
        self._missing_ids = []
        self.installed_count.set_badge("0", "neutral")
        self.warnings_box.set_text("Sin advertencias.")
        record = self._record()
        if record is None:
            self._set_busy(False, "Crea un servidor en la pestaña Servidores para gestionar sus mods.")
            return
        if record.server_type == "vanilla":
            self._set_busy(False, "Este servidor es Vanilla. Instala Fabric, Forge o NeoForge para usar mods.")
            return
        known = dict(self._side_cache)
        self._set_busy(True, "Leyendo mods…")
        run_async(lambda: self._scan(record, known),
                  lambda result: self._show_mods(token, result), self._failed)

    def _scan(self, record, known: dict[str, str]):
        mods = self._core.mods.list_mods(Path(record.server_path))
        warnings = self._core.mods.validate(mods)
        warnings += self._resource_advice(record, mods)
        missing = [mod.sha1 for mod in mods if mod.sha1 not in known]
        labels: dict[str, str] = {}
        if missing:
            try:
                owners = self._core.modrinth.installed_projects(missing)
                sides = self._core.modrinth.sides(list(set(owners.values())))
                for sha1 in missing:
                    info = sides.get(owners.get(sha1, ""))
                    labels[sha1] = side_label(info["client"], info["server"]) if info else "Desconocido"
            except Exception:
                labels = {}
        return mods, warnings, labels

    def _resource_advice(self, record, mods) -> list[str]:
        enabled = [mod for mod in mods if mod.enabled]
        jar_mb = sum(mod.path.stat().st_size for mod in enabled) / (1024 * 1024)
        java = self._core.java.probe(record.java_path) if record.java_path else None
        compatible, message = (None, "")
        if java is not None:
            compatible, message = self._core.java.check_compatibility(java, record.minecraft_version)
        advice = assess(
            mod_count=len(enabled), jar_mb=jar_mb, max_ram_mb=record.max_ram,
            system_total_mb=int(psutil.virtual_memory().total // (1024 * 1024)),
            java_present=java is not None,
            java_is_64bit=java.is_64bit if java is not None else None,
            java_compatible=compatible, java_message=message,
        )
        labels = {"error": "ERROR", "aviso": "AVISO", "info": "INFO"}
        return [f"{labels[item.level]}: {item.text}" for item in advice]

    def _show_mods(self, token: int, result) -> None:
        if token != self._token:
            return
        mods, warnings, labels = result
        self._side_cache.update(labels)
        self._mods = mods
        self.installed_count.set_badge(str(len(mods)), "green" if mods else "neutral")
        self._missing_ids = sorted(set().union(*self._core.mods.missing_dependencies(mods).values()))
        rows = []
        for mod in mods:
            state = "Activo" if mod.enabled else "Desactivado"
            side = self._side_cache.get(mod.sha1, "Sin datos")
            rows.append([mod.mod_id, mod.version, mod.loader, state, side])
        _fill(self.mod_table, rows)
        self.warnings_box.set_text("\n".join(warnings) if warnings else "Sin advertencias.")
        if not mods:
            note = "No hay mods en esta carpeta. Busca e instala desde Modrinth."
        elif self._missing_ids:
            note = "Faltan dependencias. Pulsa «Arreglar mods automáticamente» o ponlas en la carpeta mods."
        else:
            note = ""
        self._set_busy(False, note)

    def _set_busy(self, busy: bool, note: str | None = None) -> None:
        self._busy = busy
        if note is not None:
            self.note_box.set_text(note)
        self._update_buttons()

    def _update_buttons(self) -> None:
        record = self._record()
        has_server = record is not None
        mod_server = has_server and record.server_type != "vanilla"
        running = has_server and self._core.controller.is_running(record.id)
        self.ctx_bar.set_running(running, has_server)
        idle = not self._busy
        editable = idle and mod_server and not running
        has_mod = self.mod_table.currentRow() >= 0
        self.toggle_btn.setEnabled(editable and has_mod)
        self.delete_btn.setEnabled(editable and has_mod)
        self.query.setEnabled(idle and mod_server)
        self.search_btn.setEnabled(idle and mod_server)
        self.install_btn.setEnabled(editable and self.result_table.currentRow() >= 0)
        self.deps_btn.setEnabled(editable and bool(self._mods))
        self.diag_btn.setEnabled(idle and mod_server)
        self.folder_btn.setEnabled(mod_server)
        self.lock_banner.setVisible(running)

    def _failed(self, message: str) -> None:
        self._set_busy(False)
        QMessageBox.warning(self, "Operación fallida", message)

    def _open_mods_folder(self) -> None:
        record = self._record()
        if record is None:
            return
        folder = Path(record.server_path) / "mods"
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _toggle(self) -> None:
        mod, record = self._selected_mod(), self._record()
        if mod is None or record is None:
            return
        try:
            self._core.mods.set_enabled(Path(record.server_path), mod.name, not mod.enabled,
                                        running=self._core.controller.is_running(record.id))
        except (ModError, OSError) as error:
            QMessageBox.warning(self, "No se pudo cambiar el mod", str(error))
            return
        self._load_mods()

    def _delete(self) -> None:
        mod, record = self._selected_mod(), self._record()
        if mod is None or record is None:
            return
        answer = QMessageBox.question(
            self, "Eliminar mod", f"Se eliminará «{mod.name}». No se puede deshacer. ¿Continuar?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._core.mods.delete(Path(record.server_path), mod.name,
                                   running=self._core.controller.is_running(record.id), confirmed=True)
        except (ModError, OSError, PermissionError) as error:
            QMessageBox.warning(self, "No se pudo eliminar el mod", str(error))
            return
        self._load_mods()

    def _search(self) -> None:
        record = self._record()
        text = self.query.text().strip()
        if record is None or record.server_type == "vanilla" or not text:
            return
        mc, loader = record.minecraft_version, record.server_type
        self._set_busy(True, f"Buscando «{text}» en Modrinth…")
        run_async(lambda: self._core.modrinth.search(text, mc, loader), self._show_hits, self._failed)

    def _show_hits(self, hits: list[dict]) -> None:
        self._hits = hits
        rows = [[hit.get("title", "?"), (hit.get("description") or "")[:90],
                 side_label(hit.get("client_side"), hit.get("server_side"))] for hit in hits]
        _fill(self.result_table, rows)
        self._set_busy(False, f"{len(hits)} resultado(s). Revisa la columna Lado antes de instalar." if hits
                       else "Sin resultados para esta versión y este cargador.")

    def _install(self) -> None:
        row = self.result_table.currentRow()
        record = self._record()
        if row < 0 or record is None:
            return
        hit = self._hits[row]
        title = hit.get("title", "mod")
        folder = Path(record.server_path)
        mc, loader = record.minecraft_version, record.server_type
        known = [mod.sha1 for mod in self._mods if mod.enabled]
        self._set_busy(True, f"Revisando «{title}» y sus dependencias…")
        run_async(lambda: self._plan(hit["project_id"], mc, loader, known),
                  lambda result: self._after_plan(title, folder, result), self._failed)

    def _plan(self, project_id: str, minecraft_version: str, loader: str, known_sha1: list[str]):
        owners = self._core.modrinth.installed_projects(known_sha1)
        plan = self._core.modrinth.plan_project(project_id, minecraft_version, loader, set(owners.values()))
        sides = self._core.modrinth.sides([version["project_id"] for version in plan])
        return plan, sides

    def _after_plan(self, title: str, folder: Path, result) -> None:
        plan, sides = result
        blocked = []
        for version in plan:
            info = sides.get(version["project_id"], {})
            if blocks_server(info.get("server")):
                blocked.append(info.get("title", version["project_id"]))
        if blocked and not self._confirm_client_only(blocked):
            self._set_busy(False, "Instalación cancelada.")
            return
        self._set_busy(True, f"Descargando «{title}» y sus dependencias…")
        run_async(lambda: self._core.modrinth.download_plan(plan, folder / "mods"),
                  lambda paths: self._installed(title, paths), self._failed)

    def _confirm_client_only(self, names: list[str]) -> bool:
        listing = "\n".join(f"• {name}" for name in names)
        answer = QMessageBox.warning(
            self, "Mod de cliente",
            "Estos mods son solo de cliente. Si los instalas en el servidor, puede cerrarse al arrancar:\n\n"
            f"{listing}\n\n¿Instalarlos en el servidor de todos modos?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        return answer == QMessageBox.StandardButton.Yes

    def _auto_fix(self) -> None:
        record = self._record()
        if record is None or not self._mods:
            return
        folder = Path(record.server_path)
        mc, loader = record.minecraft_version, record.server_type
        self._set_busy(True, "Arreglando mods: actualizando, instalando dependencias y desactivando lo que no funcione…")
        run_async(lambda: ModDoctor(self._core.modrinth).run(folder, mc, loader),
                  self._show_fix_report, self._failed)

    def _show_fix_report(self, report) -> None:
        self._set_busy(False, "Listo: mods revisados.")
        self._load_mods()
        QMessageBox.information(self, "Arreglo automático de mods", "\n".join(report.lines()))

    def _diagnose(self) -> None:
        record = self._record()
        if record is None:
            return
        folder = Path(record.server_path)
        expected = {mod.mod_id for mod in self._mods if mod.enabled}
        self._set_busy(True, "Revisando el último arranque del servidor…")
        run_async(lambda: diagnose(folder, expected), self._show_diagnosis, self._failed)

    def _show_diagnosis(self, diagnosis) -> None:
        self._set_busy(False, "")
        QMessageBox.information(self, "Diagnóstico del servidor", "\n".join(diagnosis.lines()))

    def _installed(self, title: str, paths: list[Path]) -> None:
        self._set_busy(False, f"Listo: «{title}» con {len(paths)} archivo(s).")
        self._load_mods()