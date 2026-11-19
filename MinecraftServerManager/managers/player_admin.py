"""Administración de jugadores. La whitelist en modo offline se edita en el archivo; el resto usa comandos."""
from __future__ import annotations

import re
from pathlib import Path

NAME_RE = re.compile(r"[A-Za-z0-9_]{3,16}")  # formato válido de nombres de Minecraft
ACTIONS = {
    "whitelist_add": "whitelist add {p}",
    "whitelist_remove": "whitelist remove {p}",
    "op": "op {p}",
    "deop": "deop {p}",
    "kick": "kick {p} {r}",
    "ban": "ban {p} {r}",
    "pardon": "pardon {p}",
}
WHITELIST_ACTIONS = ("whitelist_add", "whitelist_remove")


class PlayerAdmin:
    def __init__(self, controller, operations=None, servers=None, whitelist=None) -> None:
        self._controller = controller
        self._operations = operations  # historial opcional (tabla operations)
        self._servers = servers        # permite leer si el servidor es offline
        self._whitelist = whitelist    # gestor de whitelist con UUID offline

    def run(self, server_id: int, action: str, player: str, reason: str = "") -> None:
        """Valida el nombre antes de cualquier cambio; nunca se envía texto libre sin revisar."""
        if not NAME_RE.fullmatch(player):
            raise ValueError(f"Nombre de jugador no válido: {player!r}")
        reason = reason.strip()[:100] or "Sin motivo"
        if action in WHITELIST_ACTIONS and self._servers is not None and self._whitelist is not None:
            record = self._servers.get(server_id)
            if not record.online_mode:
                self._offline_whitelist(server_id, Path(record.server_path), action, player)
                return
        template = ACTIONS[action]  # KeyError si la acción no existe
        self._controller.send_command(server_id, template.format(p=player, r=reason))
        if self._operations is not None:
            self._operations.add(server_id, f"jugador: {action}", "solicitado", f"{player} {reason}")

    def _offline_whitelist(self, server_id: int, folder: Path, action: str, player: str) -> None:
        try:
            if action == "whitelist_add":
                entry = self._whitelist.add_offline(folder, player)
                detail = f"{entry['name']} → {entry['uuid']}"
            else:
                self._whitelist.remove(folder, player)
                detail = player
        except (OSError, ValueError) as error:
            raise RuntimeError(str(error)) from error
        if self._controller.is_running(server_id):
            self._controller.send_command(server_id, "whitelist reload")  # el servidor relee el archivo
        if self._operations is not None:
            self._operations.add(server_id, f"whitelist: {action}", "ok", detail)