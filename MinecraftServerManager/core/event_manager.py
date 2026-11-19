"""Bus de eventos simple para desacoplar la lógica de la interfaz."""
from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)


class EventManager:
    def __init__(self) -> None:
        self._handlers: defaultdict[str, list[Callable[..., None]]] = defaultdict(list)

    def subscribe(self, event: str, handler: Callable[..., None]) -> None:
        self._handlers[event].append(handler)

    def publish(self, event: str, **payload: Any) -> None:
        for handler in list(self._handlers.get(event, ())):
            try:
                handler(**payload)
            except Exception:  # un suscriptor defectuoso no debe detener a los demás
                log.exception("Error en un suscriptor de '%s'", event)
