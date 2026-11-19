"""Diagnóstico de red local: comprueba si un puerto TCP está libre antes de iniciar el servidor."""
from __future__ import annotations

import socket


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("", port))
        except OSError:
            return False
        return True
