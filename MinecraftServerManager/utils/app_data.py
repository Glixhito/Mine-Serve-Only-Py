"""Carpeta de datos por usuario y migración de la versión anterior."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_NAME = "MinecraftServerManager"


def user_data_dir() -> Path:
    """%LOCALAPPDATA%\\MinecraftServerManager: escribible sin permisos de administrador."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / APP_NAME


def legacy_data_dir() -> Path | None:
    """Carpeta data\\ junto al .exe de una instalación anterior, si la hay."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "data"
    return None


def migrate_legacy(legacy: Path | None, target: Path) -> bool:
    """Copia la carpeta data de una versión anterior a target\\data, solo si aún no existe."""
    if legacy is None or not legacy.is_dir() or (target / "data").exists():
        return False
    shutil.copytree(legacy, target / "data")
    return True