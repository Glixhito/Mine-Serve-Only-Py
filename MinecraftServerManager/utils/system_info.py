"""Información básica del sistema (la Fase 5 ampliará este módulo)."""
from __future__ import annotations

import os
import platform
import sys

import psutil

MB = 1024 * 1024


def summary() -> dict[str, str]:
    memory = psutil.virtual_memory()
    return {
        "Sistema": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "Python": sys.version.split()[0],
        "RAM total": f"{memory.total // MB} MB",
        "RAM disponible": f"{memory.available // MB} MB",
        "CPU lógicas": str(os.cpu_count() or 0),
    }


def is_windows_64bit() -> bool:
    return platform.system() == "Windows" and platform.machine().endswith("64")
