"""Historial de operaciones (tabla operations). Registra acciones administrativas relevantes."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from database.connection import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class OperationRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, server_id: int | None, operation_type: str, status: str, message: str = "") -> None:
        text = message[:500]
        try:
            self._insert(server_id, operation_type, status, text)
        except sqlite3.IntegrityError:  # el servidor ya no existe: se guarda sin referencia
            self._insert(None, operation_type, status, f"[servidor eliminado] {text}".strip())

    def _insert(self, server_id: int | None, operation_type: str, status: str, message: str) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT INTO operations (server_id, operation_type, status, message, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (server_id, operation_type, status, message, _now()),
            )

    def recent(self, server_id: int | None = None, limit: int = 200) -> list[sqlite3.Row]:
        base = ("SELECT o.id, o.server_id, o.operation_type, o.status, o.message, o.created_at,"
                " s.name AS server_name FROM operations o LEFT JOIN servers s ON s.id = o.server_id")
        if server_id is None:
            return self._db.fetchall(base + " ORDER BY o.id DESC LIMIT ?", (limit,))
        return self._db.fetchall(base + " WHERE o.server_id = ? ORDER BY o.id DESC LIMIT ?",
                                 (server_id, limit))