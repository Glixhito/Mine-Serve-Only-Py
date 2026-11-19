"""Rutas de recursos empaquetados (iconos, imagenes): funcionan desde el codigo y desde el instalador."""
from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    """Ruta absoluta de un recurso. Con PyInstaller los archivos se extraen en sys._MEIPASS."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative