"""Respaldos en ZIP: manuales y automáticos, listado exacto, retención y restauración protegida."""
from __future__ import annotations

import os
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from utils import validators

EXCLUDED_DIRS = {"logs", "cache"}      # registros y caché: no se respaldan ni se borran al restaurar
EXCLUDED_SUFFIXES = {".part", ".tmp"}  # archivos a medias de descargas o escrituras


class BackupError(RuntimeError):
    """El respaldo no se puede realizar en el estado actual."""


class BackupManager:
    def __init__(self, backups_dir: Path) -> None:
        self._dir = backups_dir

    def create(self, server_dir: Path, *, running: bool, automatic: bool = False) -> Path:
        """Crea un ZIP. Con el servidor en ejecución se niega; la copia automática usa save-off antes."""
        if running:
            raise BackupError("Detén el servidor antes de respaldar para evitar archivos a medias.")
        self._dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S%f")
        tag = "auto-" if automatic else ""
        target = self._dir / f"{server_dir.name}-{tag}{stamp}.zip"
        partial = target.with_name(target.name + ".part")
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(server_dir.rglob("*")):
                rel = path.relative_to(server_dir)
                if path.is_dir() or rel.parts[0] in EXCLUDED_DIRS or path.suffix in EXCLUDED_SUFFIXES:
                    continue
                archive.write(path, rel.as_posix())
        os.replace(partial, target)
        return target

    def _entries(self, server_dir: Path) -> list[tuple[Path, bool]]:
        """(ruta, es_automático) de los respaldos de ESTE servidor, del más reciente al más antiguo."""
        if not self._dir.is_dir():
            return []
        pattern = re.compile(re.escape(server_dir.name) + r"-(?P<auto>auto-)?(?P<stamp>\d{8}-\d{12})\.zip")
        found = []
        for path in self._dir.iterdir():
            match = pattern.fullmatch(path.name)
            if match:
                found.append((match.group("stamp"), path, match.group("auto") is not None))
        found.sort(key=lambda item: item[0], reverse=True)
        return [(path, is_auto) for _stamp, path, is_auto in found]

    def list_backups(self, server_dir: Path, kind: str | None = None) -> list[Path]:
        """kind: None = todos; 'auto' = automáticos; 'manual' = manuales."""
        return [path for path, is_auto in self._entries(server_dir)
                if kind is None or (kind == "auto") == is_auto]

    def prune_automatic(self, server_dir: Path, keep: int) -> list[Path]:
        """Borra solo respaldos AUTOMÁTICOS más allá de 'keep'. Los manuales nunca se tocan."""
        if keep < 1:
            raise ValueError("Conserva al menos un respaldo automático.")
        removed = self.list_backups(server_dir, kind="auto")[keep:]
        for path in removed:
            path.unlink(missing_ok=True)
        return removed

    def delete(self, server_dir: Path, backup: Path) -> None:
        """Borra un respaldo concreto, solo si pertenece a este servidor."""
        if backup not in self.list_backups(server_dir):
            raise FileNotFoundError(f"El respaldo {backup.name} no pertenece a este servidor.")
        backup.unlink()

    def restore(self, backup: Path, server_dir: Path, *, running: bool) -> Path:
        """Restaura un ZIP. Antes guarda el estado actual como respaldo manual; los registros se conservan."""
        if running:
            raise BackupError("Detén el servidor antes de restaurar.")
        safety = self.create(server_dir, running=False)
        staging = server_dir.with_name(server_dir.name + ".restore")
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir()
        try:
            with zipfile.ZipFile(backup) as archive:
                for member in archive.namelist():
                    validators.ensure_inside(staging, staging / member)  # evita rutas que escapen (zip-slip)
                archive.extractall(staging)
            for child in server_dir.iterdir():
                if child.name in EXCLUDED_DIRS:
                    continue
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            for child in staging.iterdir():
                shutil.move(str(child), str(server_dir / child.name))
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return safety