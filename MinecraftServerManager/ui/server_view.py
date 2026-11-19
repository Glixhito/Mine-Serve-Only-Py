from __future__ import annotations

from collections import deque
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                                QListWidget, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

from ui.create_server_dialog import CreateServerDialog
from managers.preflight import check_before_start, format_conflicts, parse_port
from ui.workers import run_async

LOG_LINES = 500
POLL_MS = 2000
EULA_URL = "https://aka.ms/MinecraftEULA"
BUTTONS = [
    ("new", "Nuevo servidor"), ("eula", "Aceptar EULA"), ("start", "Iniciar"), ("stop", "Detener"),
    ("restart", "Reiniciar"), ("backup", "Respaldar"), ("restore", "Restaurar último"),
    ("duplicate", "Duplicar"), ("edit", "Editar nombre"), ("folder", "Abrir carpeta"),
    ("delete", "Eliminar"),
]


class ServerView(QWidget):
    def __init__(self, core) -> None:
        super().__init__()
        self._core = core
        self._ids: list[int] = []
        self._logs: dict[int, deque[str]] = {}
        self._busy_message: str | None = None

        self.list = QListWidget()
        self.list.setMinimumWidth(260)
        self.list.currentRowChanged.connect(self._on_select)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(2000)
        self.command = QLineEdit()
        self.command.setPlaceholderText("Comando de consola, p. ej. say hola")
        self.send_btn = QPushButton("Enviar")
        self.send_btn.clicked.connect(self._send)
        self.command.returnPressed.connect(self._send)

        handlers = {"new": self._new_server, "eula": self._accept_eula, "start": self._start,
                    "stop": self._stop, "restart": self._restart, "backup": self._backup,
                    "restore": self._restore, "duplicate": self._duplicate, "edit": self._edit,
                    "folder": self._open_folder, "delete": self._delete}
        self.buttons: dict[str, QPushButton] = {}
        grid = QGridLayout()
        for index, (key, label) in enumerate(BUTTONS):
            button = QPushButton(label)
            button.clicked.connect(handlers[key])
            self.buttons[key] = button
            grid.addWidget(button, index // 4, index % 4)

        command_row = QHBoxLayout()
        command_row.addWidget(self.command, 1)
        command_row.addWidget(self.send_btn)

        right = QVBoxLayout()
        right.addWidget(self.info)
        right.addLayout(grid)
        right.addWidget(self.console, 1)
        right.addLayout(command_row)
        root = QHBoxLayout(self)
        root.addWidget(self.list, 1)
        root.addLayout(right, 3)

        core.events.subscribe("server.log", self._on_log)
        core.events.subscribe("server.status_changed", self._on_status)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_info)
        self._timer.start(POLL_MS)
        self.refresh()

    # ----- listado y selección -------------------------------------------------
    def refresh(self) -> None:
        current = self._selected()
        self.list.blockSignals(True)
        self.list.clear()
        self._ids = []
        for record in self._core.servers.list_servers():
            self._ids.append(record.id)
            status = self._core.controller.status(record.id)
            self.list.addItem(f"{record.name} · {record.minecraft_version} · {record.server_type} · {status}")
        if current in self._ids:
            self.list.setCurrentRow(self._ids.index(current))
        self.list.blockSignals(False)
        self._on_select(self.list.currentRow())

    def _selected(self) -> int | None:
        row = self.list.currentRow()
        return self._ids[row] if 0 <= row < len(self._ids) else None

    def _on_select(self, _row: int) -> None:
        self.console.setPlainText("\n".join(self._logs.get(self._selected(), ())))
        self._update_info()

    # ----- eventos del controlador (hilo principal) ----------------------------
    def _on_log(self, server_id: int, line: str) -> None:
        self._logs.setdefault(server_id, deque(maxlen=LOG_LINES)).append(line)
        if server_id == self._selected():
            self.console.appendPlainText(line)

    def _on_status(self, server_id: int, status: str) -> None:
        self.refresh()

    def _update_info(self) -> None:
        sid = self._selected()
        idle = self._busy_message is None
        if sid is None:
            self.info.setText(self._busy_message or "Selecciona un servidor o crea uno nuevo.")
            for key, button in self.buttons.items():
                button.setEnabled(key == "new" and idle)
            self.send_btn.setEnabled(False)
            self.command.setEnabled(False)
            return
        record = self._core.servers.get(sid)
        running = self._core.controller.is_running(sid)
        has_eula = self._core.config.has_eula(Path(record.server_path))
        metrics = self._core.monitor.snapshot(self._core.controller.pid(sid))
        detail = (f"CPU {metrics['cpu_pct']} % · RAM {metrics['ram_mb']} MB · activo {metrics['uptime_s']} s"
                  if metrics else "")
        self.info.setText(self._busy_message or f"{record.name} · {self._core.controller.status(sid)} {detail}")
        enabled = {
            "new": idle,
            "eula": idle and not has_eula and not running,
            "start": idle and has_eula and not running,
            "stop": idle and running,
            "restart": idle and (running or has_eula),
            "backup": idle and not running,
            "restore": idle and not running,
            "duplicate": idle,
            "edit": idle,
            "folder": idle,
            "delete": idle and not running,
        }
        for key, button in self.buttons.items():
            button.setEnabled(enabled[key])
        self.send_btn.setEnabled(idle and running)
        self.command.setEnabled(idle and running)

    # ----- tareas en segundo plano y registro de acciones ----------------------
    def _log(self, sid: int | None, op: str, status: str, message: str = "") -> None:
        self._core.operations.add(sid, op, status, message)

    def _start_task(self, fn, message: str, on_done, op: str = "crear servidor",
                    sid: int | None = None, detail: str = "") -> None:
        """Ejecuta una tarea bloqueante en otro hilo, la registra en el historial y bloquea la vista."""
        self._busy_message = message
        self._update_info()

        def finished(result) -> None:
            self._busy_message = None
            target = sid if sid is not None else (result[0] if isinstance(result, tuple) else (result if isinstance(result, int) else None))
            self._log(target, op, "ok", detail)
            on_done(result)
            self.refresh()

        def failed(error: str) -> None:
            self._busy_message = None
            self._log(sid, op, "fallido", f"{detail} {error}".strip())
            QMessageBox.warning(self, "Operación fallida", error)
            self.refresh()

        run_async(fn, finished, failed)

    def _create_and_install(self, p: dict) -> tuple[int, str]:
        servers = self._core.servers
        record = servers.create(p["name"], p["version"], min_ram=p["min_ram"],
                                max_ram=p["max_ram"], online_mode=p["online"])
        try:
            servers.update_runtime(record.id, java_path=p["java"], min_ram=p["min_ram"], max_ram=p["max_ram"])
            if p["loader"] == "vanilla":
                servers.install_vanilla(record.id)
            else:
                self._core.loaders.install(record.id, p["loader"], p["loader_version"])
        except Exception:
            servers.delete(record.id, confirmed=True)  # deshace registro y carpeta si la instalación falla
            raise
        mod_warning = ""
        try:
            self._install_picked_mods(Path(record.server_path), p.get("mods", []), p["version"], p["loader"])
        except Exception as error:  # el servidor ya existe: un fallo de mods no lo borra
            mod_warning = str(error)
        return record.id, mod_warning

    def _install_picked_mods(self, server_dir: Path, project_ids: list[str],
                             minecraft_version: str, loader: str) -> None:
        if not project_ids:
            return
        taken: set[str] = set()
        plan: list[dict] = []
        for project_id in project_ids:
            if project_id in taken:
                continue
            for version in self._core.modrinth.plan_project(project_id, minecraft_version, loader, taken):
                if version["project_id"] not in taken:
                    taken.add(version["project_id"])
                    plan.append(version)
        mods_dir = server_dir / "mods"
        mods_dir.mkdir(parents=True, exist_ok=True)
        self._core.modrinth.download_plan(plan, mods_dir)

    def _duplicate_job(self, source_id: int, params: dict) -> int:
        new_id, _ = self._create_and_install(params)
        self._core.servers.copy_settings(source_id, new_id)
        return new_id

    # ----- acciones ------------------------------------------------------------
    def _new_server(self) -> None:
        dialog = CreateServerDialog(self._core, self)
        if not dialog.exec():
            return
        params = dialog.params
        self._start_task(
            lambda: self._create_and_install(params),
            f"Creando e instalando «{params['name']}»…",
            self._finish_create,
            op="crear servidor",
            detail=params["name"],
        )

    def _finish_create(self, result) -> None:
        _sid, mod_warning = result
        text = "Servidor instalado. Acepta la EULA para poder iniciarlo."
        if mod_warning:
            QMessageBox.warning(self, "Servidor creado", f"{text}\n\nNo se pudieron instalar los mods elegidos: "
                                f"{mod_warning}\nPuedes instalarlos desde la pestaña Mods.")
        else:
            QMessageBox.information(self, "Listo", text)

    def _accept_eula(self) -> None:
        sid = self._selected()
        if sid is None:
            return
        answer = QMessageBox.question(
            self, "EULA de Minecraft",
            f"Para ejecutar el servidor debes aceptar la EULA de Mojang ({EULA_URL}). ¿La aceptas?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._core.config.accept_eula(Path(self._core.servers.get(sid).server_path), accepted=True)
        self._log(sid, "aceptar EULA", "ok")
        self._update_info()

    def _start(self) -> None:
        sid = self._selected()
        if sid is None:
            return
        record = self._core.servers.get(sid)
        server_dir = Path(record.server_path)
        props = self._core.config.read(server_dir)
        conflicts = check_before_start(
            server_dir,
            server_port=parse_port(props.get("server-port"), 25565),
            world_name=props.get("level-name") or "world",
            already_running=self._core.controller.is_running(sid),
        )
        if conflicts:
            self._log(sid, "iniciar", "bloqueado", "; ".join(c.what for c in conflicts))
            QMessageBox.warning(self, "No se puede iniciar el servidor", format_conflicts(conflicts))
            self._update_info()
            return
        try:
            self._core.controller.start(sid)
            self._log(sid, "iniciar", "solicitado")
        except (OSError, RuntimeError, ValueError) as error:
            self._log(sid, "iniciar", "fallido", str(error))
            QMessageBox.warning(self, "No se pudo iniciar", str(error))
        self._update_info()

    def _stop(self) -> None:
        sid = self._selected()
        if sid is None:
            return
        self._core.controller.stop(sid)
        self._log(sid, "detener", "solicitado")
        self._update_info()

    def _restart(self) -> None:
        sid = self._selected()
        if sid is None:
            return
        try:
            self._core.controller.restart(sid)
            self._log(sid, "reiniciar", "solicitado")
        except (OSError, RuntimeError, ValueError) as error:
            self._log(sid, "reiniciar", "fallido", str(error))
            QMessageBox.warning(self, "No se pudo reiniciar", str(error))
        self._update_info()

    def _send(self) -> None:
        sid = self._selected()
        text = self.command.text().strip()
        if sid is None or not text:
            return
        try:
            self._core.controller.send_command(sid, text)
        except (RuntimeError, ValueError) as error:
            QMessageBox.warning(self, "Comando no enviado", str(error))
        self.command.clear()

    def _backup(self) -> None:
        sid = self._selected()
        if sid is None:
            return
        folder = Path(self._core.servers.get(sid).server_path)
        self._start_task(
            lambda: self._core.backups.create(folder, running=False),
            "Creando respaldo…",
            lambda path: QMessageBox.information(self, "Respaldo creado", str(path)),
            op="respaldar", sid=sid, detail=folder.name,
        )

    def _restore(self) -> None:
        sid = self._selected()
        if sid is None:
            return
        folder = Path(self._core.servers.get(sid).server_path)
        backups = self._core.backups.list_backups(folder)
        if not backups:
            QMessageBox.information(self, "Sin respaldos", "Este servidor aún no tiene respaldos.")
            return
        latest = backups[0]
        answer = QMessageBox.question(
            self, "Restaurar", f"Se restaurará {latest.name}. Antes se guardará el estado actual. ¿Continuar?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._start_task(
            lambda: self._core.backups.restore(latest, folder, running=False),
            "Restaurando respaldo…",
            lambda _result: QMessageBox.information(self, "Listo", "Respaldo restaurado."),
            op="restaurar", sid=sid, detail=latest.name,
        )

    def _duplicate(self) -> None:
        sid = self._selected()
        if sid is None:
            return
        record = self._core.servers.get(sid)
        if record.server_type != "vanilla" and not record.loader_version:
            QMessageBox.warning(self, "No se puede duplicar",
                                "Este servidor no tiene versión de cargador registrada.")
            return
        name, ok = QInputDialog.getText(self, "Duplicar servidor", "Nombre del nuevo servidor:",
                                        text=f"{record.name} copia")
        if not ok or not name.strip():
            return
        params = {
            "name": name.strip(), "version": record.minecraft_version, "loader": record.server_type,
            "loader_version": record.loader_version or "", "java": record.java_path or "",
            "min_ram": record.min_ram, "max_ram": record.max_ram, "online": record.online_mode,
        }
        self._start_task(
            lambda: self._duplicate_job(sid, params),
            f"Duplicando «{record.name}»…",
            lambda _new_id: QMessageBox.information(
                self, "Listo",
                "Servidor duplicado con la misma configuración. El mundo no se copió; "
                "acepta la EULA del nuevo servidor para iniciarlo."),
            op="duplicar", detail=f"desde «{record.name}»",
        )

    def _edit(self) -> None:
        sid = self._selected()
        if sid is None:
            return
        record = self._core.servers.get(sid)
        name, ok = QInputDialog.getText(self, "Editar servidor", "Nombre:", text=record.name)
        if not ok:
            return
        description, ok = QInputDialog.getText(self, "Editar servidor", "Descripción (opcional):",
                                               text=record.description)
        if not ok:
            return
        try:
            self._core.servers.edit(sid, name=name, description=description)
        except ValueError as error:
            QMessageBox.warning(self, "No se pudo editar", str(error))
            return
        self._log(sid, "editar", "ok", f"nombre: {name.strip()}")
        self.refresh()

    def _open_folder(self) -> None:
        sid = self._selected()
        if sid is None:
            return
        folder = Path(self._core.servers.get(sid).server_path)
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
            QMessageBox.warning(self, "No se pudo abrir", f"Abre esta carpeta manualmente:\n{folder}")

    def _delete(self) -> None:
        sid = self._selected()
        if sid is None:
            return
        record = self._core.servers.get(sid)
        answer = QMessageBox.question(
            self, "Eliminar servidor",
            f"Se eliminará «{record.name}» y su carpeta. Antes se creará un respaldo. ¿Continuar?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        folder = Path(record.server_path)

        def remove() -> None:
            self._core.backups.create(folder, running=False)
            self._core.servers.delete(sid, confirmed=True)

        self._start_task(remove, f"Eliminando «{record.name}»…", lambda _result: None,
                         op="eliminar", detail=f"«{record.name}»")