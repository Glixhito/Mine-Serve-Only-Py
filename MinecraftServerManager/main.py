"""Punto de entrada de Minecraft Server Manager."""
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from core.application import Application
from managers.java_installer import JavaInstaller
from managers.server_migration import repair_server_paths
from managers.setup_check import all_ok, evaluate
from managers.zerotier_installer import ZeroTierInstaller
from repositories.server_repository import ServerRepository
from ui.main_window import MainWindow
from ui.setup_dialog import SetupDialog
from utils.app_data import legacy_data_dir, migrate_legacy, user_data_dir
from utils.resources import resource_path


def base_dir() -> Path:
    """Instalado: datos del usuario en %LOCALAPPDATA%. Desde codigo: carpeta del proyecto."""
    if getattr(sys, "frozen", False):
        base = user_data_dir()
        base.mkdir(parents=True, exist_ok=True)
        migrate_legacy(legacy_data_dir(), base)
        return base
    return Path(__file__).resolve().parent


def main() -> int:
    qt_app = QApplication(sys.argv)
    icon = resource_path("assets/icono.ico")
    if icon.is_file():
        qt_app.setWindowIcon(QIcon(str(icon)))
    base = base_dir()
    core = Application(base_dir=base)
    window = MainWindow(core)
    window.show()

    fixed, missing = repair_server_paths(ServerRepository(core.db), core.paths.servers)
    if fixed or missing:
        lines = []
        if fixed:
            lines.append(f"Servidores vinculados a esta instalacion: {', '.join(fixed)}.")
        if missing:
            lines.append("No encontre la carpeta de: " + ", ".join(missing) +
                         ". Copia la carpeta data del proyecto como se indica en el manual.")
        QMessageBox.information(window, "Servidores", "\n".join(lines))

    java, zerotier = JavaInstaller(base / "runtime"), ZeroTierInstaller(base / "cache")
    dialog_needed = not all_ok(evaluate(
        java.installed_java() is not None or any(i.major >= 25 for i in core.java.detect()),
        zerotier.is_installed()))
    if dialog_needed:
        SetupDialog(core, java, zerotier, window).exec()
    return qt_app.exec()


if __name__ == "__main__":
    sys.exit(main())