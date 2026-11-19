"""Whitelist con UUID correcto. En modo offline calcula el UUID localmente, sin consultar a Mojang."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path

from utils import file_manager

WHITELIST_FILE = "whitelist.json"
NAME_RE = re.compile(r"[A-Za-z0-9_]{3,16}")


def offline_uuid(name: str) -> str:
    """UUID que Minecraft asigna en modo offline: UUID v3 del texto 'OfflinePlayer:<nombre>'."""
    digest = bytearray(hashlib.md5(f"OfflinePlayer:{name}".encode("utf-8")).digest())
    digest[6] = (digest[6] & 0x0F) | 0x30
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(digest)))


def _check_name(name: str) -> str:
    name = name.strip()
    if not NAME_RE.fullmatch(name):
        raise ValueError(f"Nombre de jugador no válido: {name!r}")
    return name


class WhitelistManager:
    def read(self, server_dir: Path) -> list[dict]:
        path = server_dir / WHITELIST_FILE
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ValueError(f"whitelist.json está dañado: {error}") from error
        if not isinstance(data, list):
            raise ValueError("whitelist.json no tiene el formato esperado.")
        return [{"uuid": str(entry.get("uuid", "")), "name": str(entry["name"])}
                for entry in data if isinstance(entry, dict) and "name" in entry]

    def _write(self, server_dir: Path, entries: list[dict]) -> None:
        text = json.dumps(entries, indent=2, ensure_ascii=False) + "\n"
        file_manager.write_text_atomic(server_dir / WHITELIST_FILE, text)

    def add_offline(self, server_dir: Path, name: str) -> dict:
        """Agrega al jugador con su UUID offline. Si ya estaba con otro UUID, lo corrige."""
        name = _check_name(name)
        player_uuid = offline_uuid(name)
        kept = [entry for entry in self.read(server_dir)
                if entry["name"].lower() != name.lower() and entry["uuid"].lower() != player_uuid]
        entry = {"uuid": player_uuid, "name": name}
        kept.append(entry)
        self._write(server_dir, kept)
        return entry

    def remove(self, server_dir: Path, name: str) -> None:
        name = _check_name(name)
        entries = self.read(server_dir)
        kept = [entry for entry in entries if entry["name"].lower() != name.lower()]
        if len(kept) == len(entries):
            raise ValueError(f"{name} no está en la whitelist.")
        self._write(server_dir, kept)