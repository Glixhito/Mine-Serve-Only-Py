"""Esquema SQLite y modelos de datos (sección 7 del documento)."""
from __future__ import annotations

from dataclasses import dataclass


class ServerStatus:
    STOPPED = "detenido"
    STARTING = "iniciando"
    ACTIVE = "activo"
    ERROR = "error"


SCHEMA = (
    """CREATE TABLE IF NOT EXISTS servers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT NOT NULL DEFAULT '',
        minecraft_version TEXT NOT NULL,
        server_type TEXT NOT NULL DEFAULT 'vanilla',
        loader_version TEXT,
        java_path TEXT,
        server_path TEXT NOT NULL UNIQUE,
        min_ram INTEGER NOT NULL,
        max_ram INTEGER NOT NULL,
        online_mode INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS backups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        server_id INTEGER NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
        file_path TEXT NOT NULL,
        backup_type TEXT NOT NULL,
        created_at TEXT NOT NULL,
        size INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS operations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        server_id INTEGER REFERENCES servers(id) ON DELETE SET NULL,
        operation_type TEXT NOT NULL,
        status TEXT NOT NULL,
        message TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setting_key TEXT NOT NULL UNIQUE,
        setting_value TEXT NOT NULL
    )""",
)


@dataclass
class ServerRecord:
    name: str
    minecraft_version: str
    server_path: str
    min_ram: int
    max_ram: int
    description: str = ""
    server_type: str = "vanilla"
    loader_version: str | None = None
    java_path: str | None = None
    online_mode: bool = True
    id: int | None = None
    created_at: str = ""
    updated_at: str = ""
