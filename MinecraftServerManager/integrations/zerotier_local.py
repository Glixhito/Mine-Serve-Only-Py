"""Control del servicio ZeroTier de este equipo mediante zerotier-cli (sin shell)."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

CANDIDATES = (
    r"C:\Program Files (x86)\ZeroTier\One\zerotier-cli.bat",
    r"C:\Program Files\ZeroTier\One\zerotier-cli.bat",
)
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
IP_PATH_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}/\d+$")


def parse_node_id(output: str) -> str:
    """'200 info <nodeId> <versión> ONLINE' -> nodeId."""
    return output.split()[2]


def parse_network(output: str, network_id: str) -> dict:
    """Busca la red en la salida de 'listnetworks'. Las columnas tienen posición fija."""
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[1] == "listnetworks" and parts[2] == network_id:
            ips = [ip.split("/")[0] for ip in parts[8:] if ip != "-"]
            return {"status": parts[5], "ip": ips[0] if ips else None}
    return {"status": "NO_UNIDO", "ip": None}


def parse_peers(output: str) -> dict[str, dict]:
    """Salida de 'listpeers': nodo -> {route: directo | relevo, latency: ms o None}.

    Supuesto a confirmar en tu equipo: cada línea es
    '200 listpeers <nodo> <ruta> <latencia> <versión> <rol>', donde la ruta es ip/puerto
    cuando hay conexión directa y '-' cuando el tráfico pasa por un relevo.
    """
    peers: dict[str, dict] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0] != "200" or parts[1] != "listpeers":
            continue
        node, path, latency = parts[2].lower(), parts[3], parts[4]
        route = "directo" if IP_PATH_RE.match(path) or ":" in path else "relevo"
        peers[node] = {"route": route, "latency": int(latency) if latency.isdigit() else None}
    return peers


class ZeroTierLocal:
    def __init__(self) -> None:
        self._cli: str | None = None

    def _find(self) -> str:
        if self._cli is None:
            found = shutil.which("zerotier-cli") or next((p for p in CANDIDATES if Path(p).is_file()), None)
            if found is None:
                raise RuntimeError("ZeroTier no está instalado en este equipo. "
                                   "Instálalo desde zerotier.com y reinicia la aplicación.")
            self._cli = found
        return self._cli

    def _run(self, *args: str) -> str:
        try:
            result = subprocess.run([self._find(), *args], capture_output=True, encoding="utf-8",
                                    errors="replace", timeout=15, check=False, creationflags=_NO_WINDOW)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RuntimeError(f"No se pudo ejecutar zerotier-cli: {error}") from error
        output = result.stdout.strip()
        if not output.startswith("200"):
            raise RuntimeError(f"ZeroTier respondió «{output or result.stderr.strip()}». "
                               "Prueba a ejecutar la aplicación como administrador.")
        return output

    def node_id(self) -> str:
        return parse_node_id(self._run("info"))

    def leave(self, network_id: str) -> None:
        self._run("leave", network_id)
        
    def join(self, network_id: str) -> None:
        self._run("join", network_id)

    def network_info(self, network_id: str) -> dict:
        return parse_network(self._run("listnetworks"), network_id)

    def peers(self) -> dict[str, dict]:
        return parse_peers(self._run("listpeers"))