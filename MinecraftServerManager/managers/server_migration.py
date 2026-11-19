"""Migración de servidores creados con una versión anterior: corrige las rutas guardadas en la base de datos."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path


def repair_server_paths(repository, servers_dir: Path) -> tuple[list[str], list[str]]:
    """Hace que cada servidor use la copia que está dentro de servers_dir.

    Devuelve (corregidos, sin copia): nombres de los servidores que cambiaron de ruta y de los que no
    tienen carpeta ni en la ruta antigua ni en la instalación.
    """
    fixed: list[str] = []
    missing: list[str] = []
    for record in repository.list_all():
        current = Path(record.server_path)
        candidate = servers_dir / current.name
        if candidate.is_dir():
            if current.resolve() != candidate.resolve():
                repository.update(replace(record, server_path=str(candidate.resolve())))
                fixed.append(record.name)
        elif not current.exists():
            missing.append(record.name)
    return fixed, missing