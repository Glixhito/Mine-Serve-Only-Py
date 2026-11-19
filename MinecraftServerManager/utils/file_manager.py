"""Utilidades de archivos: hash, escritura atómica y nombres seguros para carpetas."""
from __future__ import annotations

import hashlib
import os
import re
import unicodedata
from pathlib import Path


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or "servidor"


def sha1_of(path: Path) -> str:
    """Hash por bloques de 1 MB: no carga el archivo completo en memoria."""
    digest = hashlib.sha1()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_text_atomic(path: Path, content: str) -> None:
    """Escribe en un temporal y reemplaza el destino al final, evitando archivos a medias."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(content, encoding="utf-8")
    os.replace(temp, path)
