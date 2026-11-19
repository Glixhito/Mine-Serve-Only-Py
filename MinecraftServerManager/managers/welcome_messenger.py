"""Mensaje de bienvenida propio: al entrar un jugador, la app le envía mensajes en el chat y un título en pantalla.

Funciona mientras la app tenga el servidor en ejecución, porque usa su consola. No necesita mods.
"""
from __future__ import annotations

import json
import logging
import re

log = logging.getLogger(__name__)

# Formatos que escribe el servidor (con y sin «System chat:»). Un mensaje de chat lleva <Nombre> antes,
# así que no activa el mensaje.
JOIN_RE = re.compile(r"\]: (?:System chat: )?(?P<name>[A-Za-z0-9_]{3,16}) joined the game\s*$")

DEFAULT_LINES = (
    "¡Bienvenido al servidor, {player}!",
    "Respeta a los demás jugadores y pide ayuda en el chat si la necesitas.",
)
# Título grande en el centro de la pantalla: (título, subtítulo). None para no mostrarlo.
DEFAULT_TITLE: tuple[str, str] | None = ("¡Bienvenido!", "{player}, disfruta el servidor")


class WelcomeMessenger:
    def __init__(self, events, controller, lines: tuple[str, ...] = DEFAULT_LINES,
                 title: tuple[str, str] | None = DEFAULT_TITLE) -> None:
        self._controller = controller
        self._lines = lines
        self._title = title
        events.subscribe("server.log", self._on_log)

    def _on_log(self, server_id: int, line: str) -> None:
        match = JOIN_RE.search(line)
        if match is None:
            if "joined the game" in line:
                log.info("Bienvenida: línea de entrada no reconocida en el servidor %s: %r", server_id, line)
            return
        player = match.group("name")
        if not self._controller.is_running(server_id):
            log.info("Bienvenida: %s entró, pero el servidor %s no figura como activo", player, server_id)
            return
        log.info("Bienvenida: enviando mensajes a %s en el servidor %s", player, server_id)
        self._greet(server_id, player)

    def _greet(self, server_id: int, player: str) -> None:
        for template in self._lines:
            text = template.replace("{player}", player)
            payload = json.dumps({"text": text, "color": "gold"}, ensure_ascii=False)
            self._controller.send_command(server_id, f"tellraw {player} {payload}")
        if self._title is not None:
            self._show_title(server_id, player, *self._title)

    def _show_title(self, server_id: int, player: str, title: str, subtitle: str) -> None:
        # Tiempos en ticks (20 por segundo): entrada 0,5 s, visible 4 s, salida 1 s.
        self._controller.send_command(server_id, f"title {player} times 10 80 20")
        title_style = {"text": title.replace("{player}", player), "color": "gold", "bold": True}
        subtitle_style = {"text": subtitle.replace("{player}", player), "color": "white"}
        self._controller.send_command(server_id, f"title {player} title {json.dumps(title_style, ensure_ascii=False)}")
        self._controller.send_command(server_id, f"title {player} subtitle {json.dumps(subtitle_style, ensure_ascii=False)}")