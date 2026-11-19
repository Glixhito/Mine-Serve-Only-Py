"""Red ZeroTier compartida: una sola red para todos los servidores. Se une cuando hay algún servidor
activo y sale cuando no queda ninguno."""
from __future__ import annotations

import json
import re
from pathlib import Path

from database.models import ServerStatus
from integrations.zerotier_api import ZeroTierCentral, ZeroTierError
from integrations.zerotier_local import ZeroTierLocal
from utils import file_manager

TOKEN_KEY = "zerotier_token"
NETWORK_KEY = "zerotier_network"
NODE_RE = re.compile(r"[0-9a-f]{10}")
NETWORK_RE = re.compile(r"[0-9a-f]{16}")
NO_TOKEN_HINT = "Sin token no se puede autorizar desde la app. En ZeroTier Central, abre Members y marca Auth."


def _normalize_node(node_id: str) -> str:
    node = node_id.strip().lower()
    if not NODE_RE.fullmatch(node):
        raise ValueError("El ID de nodo tiene 10 caracteres hexadecimales (0-9 y a-f).")
    return node


class ZeroTierManager:
    def __init__(self, settings, servers, operations, events, config, central=None, local=None) -> None:
        self._settings = settings
        self._servers = servers
        self._operations = operations
        self._config = config
        self._central = central  # cliente de la API; si es None se crea con el token guardado
        self._local = local or ZeroTierLocal()
        self._running: set[int] = set()  # servidores activos que necesitan la red
        events.subscribe("server.status_changed", self._on_status)

    # ----- token y red compartida ----------------------------------------------
    def token(self) -> str:
        return self._settings.get(TOKEN_KEY) or ""

    def save_token(self, token: str) -> None:
        self._settings.set(TOKEN_KEY, token.strip())

    def can_authorize(self) -> bool:
        return self._central is not None or bool(self.token())

    def network_of(self, server_id: int | None = None) -> str | None:
        """Una sola red para todos los servidores. server_id se conserva por compatibilidad."""
        return self._settings.get(NETWORK_KEY)

    def set_network(self, server_id: int, network_id: str) -> None:
        """Usa una red que ya creaste en ZeroTier Central. Sirve para todos los servidores."""
        network_id = network_id.strip().lower()
        if not NETWORK_RE.fullmatch(network_id):
            raise ValueError("El ID de red tiene 16 caracteres hexadecimales (0-9 y a-f).")
        self._settings.set(NETWORK_KEY, network_id)
        self._log(server_id, "red zerotier", "ok", f"red compartida: {network_id}")

    def _api(self) -> ZeroTierCentral:
        if self._central is not None:
            return self._central
        if not self.token():
            raise ZeroTierError("Sin token de API: pega el ID de una red existente o crea la red a mano.")
        return ZeroTierCentral(self.token())

    def _log(self, server_id: int, operation: str, status: str, message: str = "") -> None:
        self._operations.add(server_id, operation, status, message)

    # ----- crear, unir y salir -------------------------------------------------
    def provision(self, record) -> str | None:
        """Crea la red compartida si aún no existe. Con un servidor nuevo, reutiliza la que ya hay."""
        existing = self.network_of()
        if existing:
            return existing
        try:
            network = self._api().create_network(f"MSM-{file_manager.slugify(record.name)}")
        except (ZeroTierError, RuntimeError, OSError, KeyError) as error:
            self._log(record.id, "red zerotier", "fallido", str(error))
            return None
        self._settings.set(NETWORK_KEY, network)
        self._log(record.id, "red zerotier", "ok", f"red compartida creada: {network}")
        return network

    def join(self, server_id: int) -> dict:
        """Une este equipo a la red. Si hay token, autoriza el nodo; si no, queda esperando Auth manual."""
        network = self.network_of()
        if network is None:
            raise ZeroTierError("No hay red ZeroTier. Pega el ID de red en la pestaña ZeroTier.")
        self._local.join(network)
        info = self._local.network_info(network)
        if info["status"] == "ACCESS_DENIED" and self.can_authorize():
            self._api().authorize_member(network, self._local.node_id())
            info = self._local.network_info(network)
        return info

    def address(self, server_id: int) -> dict:
        """Dirección de este servidor: IP de la red compartida y el puerto propio del servidor."""
        network = self.network_of()
        if network is None:
            return {"network": None, "ip": None, "status": "sin red", "minecraft": None}
        record = self._servers.get(server_id)
        port = self._config.read(Path(record.server_path)).get("server-port", "25565")
        info = self._local.network_info(network)
        ip = info["ip"]
        return {"network": network, "ip": ip, "status": info["status"],
                "minecraft": f"{ip}:{port}" if ip else None}

    # ----- amigos ----------------------------------------------------------------
    def friends(self, server_id: int) -> list[dict]:
        raw = self._settings.get(f"zerotier_friends:{server_id}")
        return json.loads(raw) if raw else []

    def _save_friends(self, server_id: int, friends: list[dict]) -> None:
        self._settings.set(f"zerotier_friends:{server_id}", json.dumps(friends))

    def register_friend(self, server_id: int, node_id: str, name: str = "") -> None:
        """Guarda al amigo y su ID de nodo. No lo autoriza: eso se hace en ZeroTier Central o con token."""
        node = _normalize_node(node_id)
        label = name.strip()[:40] or node
        friends = [friend for friend in self.friends(server_id) if friend["node"] != node]
        friends.append({"node": node, "name": label})
        self._save_friends(server_id, friends)
        self._log(server_id, "zerotier amigo", "ok", f"{label} ({node})")

    def remove_friend(self, server_id: int, node_id: str) -> None:
        node = _normalize_node(node_id)
        friends = self.friends(server_id)
        kept = [friend for friend in friends if friend["node"] != node]
        if len(kept) == len(friends):
            raise ValueError("Ese amigo no está en la lista.")
        self._save_friends(server_id, kept)
        self._log(server_id, "zerotier amigo", "ok", f"quitado: {node}")

    def authorize_friend(self, server_id: int, node_id: str, name: str = "") -> None:
        network = self.network_of()
        if network is None:
            raise ZeroTierError("No hay red ZeroTier configurada.")
        if not self.can_authorize():
            raise ZeroTierError(NO_TOKEN_HINT)
        node = _normalize_node(node_id)
        self._api().authorize_member(network, node)
        self.register_friend(server_id, node, name)

    def friends_status(self, server_id: int) -> list[dict]:
        """Cada amigo con su conexión (directa o por relevo) y su latencia, leídas con zerotier-cli."""
        try:
            peers = self._local.peers()
        except RuntimeError:
            peers = None
        rows = []
        for friend in self.friends(server_id):
            if peers is None:
                route, latency = "desconocido", None
            elif friend["node"] not in peers:
                route, latency = "sin conexión", None
            else:
                route, latency = peers[friend["node"]]["route"], peers[friend["node"]]["latency"]
            rows.append({"name": friend["name"], "node": friend["node"], "route": route, "latency": latency})
        return rows

    # ----- eventos: se une al activarse un servidor y sale al apagar el último ---
    def _on_status(self, server_id: int, status: str) -> None:
        if status == ServerStatus.ACTIVE:
            if self.network_of() is None:
                return
            self._running.add(server_id)
            try:
                info = self.join(server_id)
                self._log(server_id, "zerotier unir", "ok", f"estado: {info['status']}")
            except (ZeroTierError, RuntimeError, OSError, ValueError) as error:
                self._log(server_id, "zerotier unir", "fallido", str(error))
        elif status in (ServerStatus.STOPPED, ServerStatus.ERROR):
            if server_id not in self._running:
                return
            self._running.discard(server_id)
            if not self._running:
                self._leave(server_id)

    def _leave(self, server_id: int) -> None:
        network = self.network_of()
        if network is None:
            return
        try:
            self._local.leave(network)
            self._log(server_id, "zerotier salir", "ok", "ningún servidor activo usa la red")
        except (RuntimeError, OSError) as error:
            self._log(server_id, "zerotier salir", "fallido", str(error))