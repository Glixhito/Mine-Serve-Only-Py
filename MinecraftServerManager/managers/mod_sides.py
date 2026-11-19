"""Lado de cada mod (cliente, servidor o ambos) a partir de los datos de Modrinth."""
from __future__ import annotations


def side_label(client: str | None, server: str | None) -> str:
    """Texto para la columna 'Lado'. Valores de Modrinth: required, optional, unsupported, unknown."""
    client = client or "unknown"
    server = server or "unknown"
    if client == "unsupported" and server == "unsupported":
        return "Sin soporte"
    if server == "unsupported":
        return "Cliente"
    if client == "unsupported":
        return "Servidor"
    if client == "unknown" and server == "unknown":
        return "Desconocido"
    return "Ambos"


def blocks_server(server: str | None) -> bool:
    """True si el mod no funciona en servidor: hay que pedir confirmación antes de instalarlo ahí."""
    return server == "unsupported"