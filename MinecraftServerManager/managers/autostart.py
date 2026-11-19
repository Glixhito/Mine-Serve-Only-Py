"""Arranque automático: al abrir la aplicación se inician los servidores marcados por el usuario."""
from __future__ import annotations


class AutostartStore:
    def __init__(self, settings) -> None:
        self._settings = settings

    @staticmethod
    def _key(server_id: int) -> str:
        return f"autostart:{server_id}"

    def is_enabled(self, server_id: int) -> bool:
        return self._settings.get(self._key(server_id)) == "1"

    def set_enabled(self, server_id: int, enabled: bool) -> None:
        self._settings.set(self._key(server_id), "1" if enabled else "0")


def start_marked_servers(core) -> list[str]:
    """Inicia los servidores marcados. Devuelve un mensaje por cada servidor que no pudo arrancar."""
    store = AutostartStore(core.settings)
    problems: list[str] = []
    for record in core.servers.list_servers():
        if not store.is_enabled(record.id):
            continue
        try:
            core.controller.start(record.id)
            core.operations.add(record.id, "autoinicio", "solicitado")
        except (OSError, RuntimeError, ValueError) as error:
            core.operations.add(record.id, "autoinicio", "fallido", str(error))
            problems.append(f"{record.name}: {error}")
    return problems