"""Política de respaldos automáticos por servidor: frecuencia, retención y cuándo toca la siguiente."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timedelta

from repositories.settings_repository import SettingsRepository

INTERVAL_RANGE = (1, 168)  # horas
KEEP_RANGE = (1, 100)      # respaldos automáticos a conservar


@dataclass
class BackupPolicy:
    enabled: bool = False
    interval_hours: int = 12
    keep: int = 10
    last_run: str | None = None  # ISO 8601 con zona horaria (UTC)

    def is_due(self, now: datetime) -> bool:
        if not self.enabled:
            return False
        if self.last_run is None:
            return True
        return now - datetime.fromisoformat(self.last_run) >= timedelta(hours=self.interval_hours)


def _check(value: int, limits: tuple[int, int], name: str) -> int:
    number = int(value)
    low, high = limits
    if not low <= number <= high:
        raise ValueError(f"{name} debe estar entre {low} y {high}.")
    return number


class BackupPolicyStore:
    def __init__(self, settings: SettingsRepository) -> None:
        self._settings = settings

    @staticmethod
    def _key(server_id: int) -> str:
        return f"backup_policy:{server_id}"

    def get(self, server_id: int) -> BackupPolicy:
        raw = self._settings.get(self._key(server_id))
        if not raw:
            return BackupPolicy()
        try:
            data = json.loads(raw)
            allowed = {field.name for field in fields(BackupPolicy)}
            return BackupPolicy(**{key: value for key, value in data.items() if key in allowed})
        except (ValueError, TypeError):
            return BackupPolicy()

    def save(self, server_id: int, policy: BackupPolicy) -> None:
        policy.interval_hours = _check(policy.interval_hours, INTERVAL_RANGE, "La frecuencia")
        policy.keep = _check(policy.keep, KEEP_RANGE, "La retención")
        self._settings.set(self._key(server_id), json.dumps(asdict(policy)))