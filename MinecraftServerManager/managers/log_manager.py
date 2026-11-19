"""Registros de la aplicación con rotación de archivos."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_configured = False


def setup_logging(log_dir: Path, level: int = logging.INFO) -> None:
    global _configured
    if _configured:
        return
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(_FORMAT)
    file_handler = RotatingFileHandler(
        log_dir / "app.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8",
    )
    console = logging.StreamHandler()
    root = logging.getLogger()
    for handler in (file_handler, console):
        handler.setFormatter(formatter)
        root.addHandler(handler)
    root.setLevel(level)
    _configured = True


def server_log_file(server_dir: Path) -> Path:
    """Registro que Minecraft escribe en cada servidor."""
    return server_dir / "logs" / "latest.log"
