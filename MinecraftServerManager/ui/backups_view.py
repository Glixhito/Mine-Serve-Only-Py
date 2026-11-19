"""Vista de respaldos: política automática, lista de copias y acciones."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QLabel,
                               QMessageBox, QPushButton, QSpinBox, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from managers.backup_policy import BackupPolicy
from ui.widgets.components import (Badge, LockBanner, NoticeBox, PageHeader, Panel,
                                   ServerContextBar, style_button)
from ui.workers import run_async

INTERVALS = [("Cada 6 horas", 6), ("Cada 12 horas", 12), ("Cada 24 horas", 24)]
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _when(path: Path) -> str:
    """Fecha del respaldo a partir del nombre; si el nombre no sigue el formato, usa la fecha del archivo."""
    try:
        _prefix, date, time = path.stem.rsplit("-", 2)
        return datetime.strptime(date + time, "%Y%m%d%H%M%S%f").strftime(DATE_FORMAT)
    except ValueError:
        pass
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime(DATE_FORMAT)
    except OSError:
        return "—"


def _kind(path: Path) -> str:
    return "Automático" if "-auto-" in path.name else "Manual"


class BackupsView(QWidget):
    def __init__(self, core) -> None:
        super().__init__()
        self._core = core
        self._ids: list[int] = []
        self._backups: list[Path] = []
        self._busy = False

        refresh_btn = QPushButton("Actualizar")
        style_button(refresh_btn, "default", "refresh")
        refresh_btn.clicked.connect(self.refresh)

        header = PageHeader(
            "Respaldos",
            "Tus mundos, a salvo. Juega con tranquilidad.",
            action_widget=refresh_btn,
        )

        self.ctx_bar = ServerContextBar(show_status=True)
        self.server_box = self.ctx_bar.combo
        self.ctx_bar.changed.connect(self.refresh)

        self.lock_banner = LockBanner(
            "El servidor está en ejecución: deténlo para respaldar o restaurar a mano. "
            "Los respaldos automáticos sí se hacen con el servidor encendido."
        )
        self.status_box = NoticeBox("", "green")
        self.status_box.setVisible(False)

        # --- Panel Política automática ---
        policy_panel = Panel("Política de respaldo automático", "clock")
        self.enabled = QCheckBox("Respaldo automático activado")
        self.interval = QComboBox()
        for label, hours in INTERVALS:
            self.interval.addItem(label, hours)
        self.keep = QSpinBox()
        self.keep.setRange(1, 100)
        self.keep.setSuffix(" copias")
        save_policy = QPushButton("Guardar política")
        style_button(save_policy, "primary", "check")
        save_policy.clicked.connect(self._save_policy)

        p_row = QHBoxLayout()
        p_row.setSpacing(14)
        p_row.addWidget(self.enabled)
        p_row.addStretch()
        p_row.addWidget(QLabel("Frecuencia:"))
        p_row.addWidget(self.interval)
        p_row.addWidget(QLabel("Conservar últimos:"))
        p_row.addWidget(self.keep)
        p_row.addWidget(save_policy)
        policy_panel.body_layout.addLayout(p_row)

        # --- Panel Tabla de respaldos ---
        self.count_badge = Badge("0 copias", "neutral")
        table_panel = Panel("Respaldos del servidor", "archive", aside=self.count_badge)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Archivo", "Tipo", "Fecha", "Tamaño"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._update_buttons)

        self.now_btn = QPushButton("Respaldar ahora")
        style_button(self.now_btn, "primary", "archive")
        self.now_btn.clicked.connect(self._backup_now)
        self.restore_btn = QPushButton("Restaurar seleccionado")
        style_button(self.restore_btn, "default", "refresh")
        self.restore_btn.clicked.connect(self._restore)
        self.delete_btn = QPushButton("Eliminar seleccionado")
        style_button(self.delete_btn, "danger-subtle", "trash")
        self.delete_btn.clicked.connect(self._delete)

        actions = QHBoxLayout()
        actions.addWidget(self.now_btn)
        actions.addWidget(self.restore_btn)
        actions.addStretch()
        actions.addWidget(self.delete_btn)

        table_panel.body_layout.addWidget(self.table, 1)
        table_panel.body_layout.addLayout(actions)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(14)
        root.addWidget(header)
        root.addWidget(self.ctx_bar)
        root.addWidget(self.lock_banner)
        root.addWidget(self.status_box)
        root.addWidget(policy_panel)
        root.addWidget(table_panel, 1)
        self.refresh()

    def _current_id(self) -> int | None:
        index = self.server_box.currentIndex()
        return self._ids[index] if 0 <= index < len(self._ids) else None

    def _record(self):
        sid = self._current_id()
        return self._core.servers.get(sid) if sid is not None else None

    def _selected_backup(self) -> Path | None:
        row = self.table.currentRow()
        return self._backups[row] if 0 <= row < len(self._backups) else None

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
        self._load_policy()
        self._load_table()
        self._update_buttons()

    def _load_policy(self) -> None:
        record = self._record()
        if record is None:
            self.enabled.setChecked(False)
            return
        policy = self._core.policies.get(record.id)
        self.enabled.setChecked(policy.enabled)
        index = self.interval.findData(policy.interval_hours)
        self.interval.setCurrentIndex(index if index >= 0 else 1)
        self.keep.setValue(policy.keep)

    def _load_table(self) -> None:
        self.table.setRowCount(0)
        self._backups = []
        record = self._record()
        if record is None:
            self.count_badge.set_badge("0 copias", "neutral")
            return
        self._backups = self._core.backups.list_backups(Path(record.server_path))
        self.count_badge.set_badge(f"{len(self._backups)} copia(s)", "blue" if self._backups else "neutral")
        self.table.setRowCount(len(self._backups))
        for row, path in enumerate(self._backups):
            try:
                size = f"{path.stat().st_size / (1024 * 1024):.1f} MB"
            except OSError:
                size = "—"
            for column, text in enumerate([path.name, _kind(path), _when(path), size]):
                self.table.setItem(row, column, QTableWidgetItem(text))

    def _save_policy(self) -> None:
        record = self._record()
        if record is None:
            return
        current = self._core.policies.get(record.id)
        enabling = self.enabled.isChecked() and not current.enabled
        policy = BackupPolicy(
            enabled=self.enabled.isChecked(),
            interval_hours=int(self.interval.currentData()),
            keep=self.keep.value(),
            last_run=current.last_run,
        )
        if enabling:
            policy.last_run = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            self._core.policies.save(record.id, policy)
        except ValueError as error:
            QMessageBox.warning(self, "Política no válida", str(error))
            return
        if policy.enabled:
            self.status_box.set_text(f"Política guardada. La primera copia automática será en {policy.interval_hours} h.")
        else:
            self.status_box.set_text("Respaldos automáticos desactivados.")

    def _run(self, fn, message: str, op: str, sid: int, detail: str, done_text) -> None:
        self._busy = True
        self.status_box.set_text(message)
        self._update_buttons()

        def finished(result) -> None:
            self._busy = False
            self._core.operations.add(sid, op, "ok", detail)
            self.status_box.set_text(done_text(result))
            self.refresh()

        def failed(error: str) -> None:
            self._busy = False
            self._core.operations.add(sid, op, "fallido", f"{detail} {error}".strip())
            self.status_box.set_text(f"No se completó: {error}")
            self.refresh()

        run_async(fn, finished, failed)

    def _backup_now(self) -> None:
        record = self._record()
        if record is None or self._core.controller.is_running(record.id):
            return
        folder = Path(record.server_path)
        self._run(lambda: self._core.backups.create(folder, running=False),
                  "Creando respaldo…", "respaldar", record.id, folder.name,
                  lambda path: f"Respaldo creado: {path.name}")

    def _restore(self) -> None:
        record = self._record()
        backup = self._selected_backup()
        if record is None or backup is None or self._core.controller.is_running(record.id):
            return
        answer = QMessageBox.question(
            self, "Restaurar respaldo",
            f"Se restaurará {backup.name}. El estado actual se guardará antes como respaldo manual. ¿Continuar?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        folder = Path(record.server_path)
        self._run(lambda: self._core.backups.restore(backup, folder, running=False),
                  "Restaurando respaldo…", "restaurar", record.id, backup.name,
                  lambda _result: "Respaldo restaurado.")

    def _delete(self) -> None:
        record = self._record()
        backup = self._selected_backup()
        if record is None or backup is None:
            return
        answer = QMessageBox.question(self, "Eliminar respaldo",
                                      f"Se eliminará {backup.name}. No se puede deshacer. ¿Continuar?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        folder = Path(record.server_path)
        self._run(lambda: self._core.backups.delete(folder, backup),
                  "Eliminando respaldo…", "eliminar respaldo", record.id, backup.name,
                  lambda _result: "Respaldo eliminado.")

    def _update_buttons(self) -> None:
        record = self._record()
        has_server = record is not None
        running = has_server and self._core.controller.is_running(record.id)
        self.ctx_bar.set_running(running, has_server)
        has_backup = self._selected_backup() is not None
        idle = not self._busy
        self.now_btn.setEnabled(idle and has_server and not running)
        self.restore_btn.setEnabled(idle and has_backup and not running)
        self.delete_btn.setEnabled(idle and has_backup)
        self.lock_banner.setVisible(running)