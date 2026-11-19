"""Lectura y escritura validada de server.properties y eula.txt."""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from utils import file_manager, validators as v

PROPERTIES_FILE = "server.properties"
EULA_FILE = "eula.txt"

# Solo estas claves pueden modificarse; cada una tiene su validador.
RULES = {
    "online-mode": v.boolean,
    "white-list": v.boolean,
    "pvp": v.boolean,
    "server-port": lambda x: v.int_in_range(x, 1, 65535),
    "max-players": lambda x: v.int_in_range(x, 1, 1000),
    "spawn-protection": lambda x: v.int_in_range(x, 0, 1000),
    "view-distance": lambda x: v.int_in_range(x, 2, 32),
    "simulation-distance": lambda x: v.int_in_range(x, 3, 32),
    "difficulty": lambda x: v.choice(x, ("peaceful", "easy", "normal", "hard")),
    "gamemode": lambda x: v.choice(x, ("survival", "creative", "adventure", "spectator")),
    "level-name": v.level_name,
    "motd": lambda x: v.text(x, 200),
    "level-seed": lambda x: v.text(x, 64),
    "level-type": lambda x: v.choice(x, ("minecraft:normal", "minecraft:flat",
                                         "minecraft:large_biomes", "minecraft:amplified")),
}
DEFAULTS = {
    "white-list": "true", "server-port": "25565", "max-players": "20", "pvp": "true",
    "spawn-protection": "16", "view-distance": "10", "simulation-distance": "10",
    "difficulty": "easy", "gamemode": "survival", "level-name": "world",
    "motd": "Servidor Minecraft",
}


class ConfigManager:
    def read(self, server_dir: Path) -> dict[str, str]:
        path = server_dir / PROPERTIES_FILE
        if not path.is_file():
            return {}
        props: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                props[key.strip()] = value.strip()
        return props

    def write(self, server_dir: Path, changes: dict[str, str]) -> dict[str, str]:
        """Valida los cambios, guarda copia del archivo anterior y escribe de forma atómica."""
        validated: dict[str, str] = {}
        for key, value in changes.items():
            if key not in RULES:
                raise ValueError(f"Propiedad no permitida: {key}")
            validated[key] = RULES[key](value)
        path = server_dir / PROPERTIES_FILE
        merged = {**self.read(server_dir), **validated}
        if path.exists():
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S%f")
            shutil.copy2(path, path.with_name(f"{PROPERTIES_FILE}.{stamp}.bak"))
            self._prune_backups(server_dir)
        body = "\n".join(f"{k}={val}" for k, val in sorted(merged.items()))
        file_manager.write_text_atomic(path, "#Generado por Minecraft Server Manager\n" + body + "\n")
        return merged

    def _prune_backups(self, server_dir: Path, keep: int = 5) -> None:
        """Conserva solo las últimas copias de server.properties para no llenar la carpeta."""
        for stale in sorted(server_dir.glob(f"{PROPERTIES_FILE}.*.bak"))[:-keep]:
            stale.unlink(missing_ok=True)

    def create_default(self, server_dir: Path, online_mode: bool) -> None:
        if (server_dir / PROPERTIES_FILE).exists():
            raise FileExistsError("server.properties ya existe.")
        self.write(server_dir, {**DEFAULTS, "online-mode": "true" if online_mode else "false"})

    def has_eula(self, server_dir: Path) -> bool:
        path = server_dir / EULA_FILE
        return path.is_file() and any(
            line.strip().lower() == "eula=true"
            for line in path.read_text(encoding="utf-8").splitlines()
        )

    def accept_eula(self, server_dir: Path, *, accepted: bool) -> None:
        """Escribe eula=true solo con aceptación explícita (True). Nunca por defecto."""
        if accepted is not True:
            raise PermissionError("La EULA solo puede aceptarse mediante confirmación explícita del usuario.")
        file_manager.write_text_atomic(server_dir / EULA_FILE, "eula=true\n")
