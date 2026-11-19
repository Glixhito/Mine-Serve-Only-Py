"""Acceso a la tabla servers (solo SQL). Las lecturas pasan por el candado de Database."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from database.connection import Database
from database.models import ServerRecord


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _to_record(row: sqlite3.Row) -> ServerRecord:
    return ServerRecord(
        id=row["id"], name=row["name"], description=row["description"],
        minecraft_version=row["minecraft_version"], server_type=row["server_type"],
        loader_version=row["loader_version"], java_path=row["java_path"],
        server_path=row["server_path"], min_ram=row["min_ram"], max_ram=row["max_ram"],
        online_mode=bool(row["online_mode"]), created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class ServerRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def insert(self, record: ServerRecord) -> ServerRecord:
        now = _now()
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO servers (name, description, minecraft_version, server_type,"
                " loader_version, java_path, server_path, min_ram, max_ram, online_mode,"
                " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (record.name, record.description, record.minecraft_version, record.server_type,
                 record.loader_version, record.java_path, record.server_path, record.min_ram,
                 record.max_ram, int(record.online_mode), now, now),
            )
            record.id = cursor.lastrowid
        record.created_at = record.updated_at = now
        return record

    def get(self, server_id: int) -> ServerRecord | None:
        rows = self._db.fetchall("SELECT * FROM servers WHERE id = ?", (server_id,))
        return _to_record(rows[0]) if rows else None

    def list_all(self) -> list[ServerRecord]:
        rows = self._db.fetchall("SELECT * FROM servers ORDER BY name")
        return [_to_record(row) for row in rows]

    def update(self, record: ServerRecord) -> None:
        now = _now()
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE servers SET name = ?, description = ?, server_type = ?, loader_version = ?,"
                " java_path = ?, min_ram = ?, max_ram = ?, online_mode = ?, updated_at = ?"
                " WHERE id = ?",
                (record.name, record.description, record.server_type, record.loader_version,
                 record.java_path, record.min_ram, record.max_ram, int(record.online_mode),
                 now, record.id),
            )
        record.updated_at = now

    def delete(self, server_id: int) -> None:
        with self._db.transaction() as conn:
            conn.execute("DELETE FROM servers WHERE id = ?", (server_id,))
