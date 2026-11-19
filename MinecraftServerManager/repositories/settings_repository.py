"""Preferencias guardadas en la tabla settings (clave y valor de texto)."""
from __future__ import annotations

from database.connection import Database


class SettingsRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get(self, key: str) -> str | None:
        rows = self._db.fetchall("SELECT setting_value FROM settings WHERE setting_key = ?", (key,))
        return rows[0]["setting_value"] if rows else None

    def set(self, key: str, value: str) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                "INSERT INTO settings (setting_key, setting_value) VALUES (?, ?)"
                " ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value",
                (key, value),
            )