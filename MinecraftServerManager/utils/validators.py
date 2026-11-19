"""Validaciones reutilizables. Todas lanzan ValueError con un mensaje legible."""
from __future__ import annotations

import re
from pathlib import Path

_NAME_RE = re.compile(r"[\w .-]{1,40}")
_LEVEL_RE = re.compile(r"[A-Za-z0-9_ -]{1,64}")


def server_name(value: str) -> str:
    value = value.strip()
    if not _NAME_RE.fullmatch(value):
        raise ValueError("El nombre admite de 1 a 40 letras, números, espacios, puntos o guiones.")
    return value


def int_in_range(value, minimum: int, maximum: int) -> str:
    try:
        number = int(str(value).strip())
    except ValueError:
        raise ValueError(f"Se esperaba un número entero, no {value!r}.") from None
    if not minimum <= number <= maximum:
        raise ValueError(f"El valor debe estar entre {minimum} y {maximum}.")
    return str(number)


def boolean(value) -> str:
    normalized = str(value).strip().lower()
    if normalized not in ("true", "false"):
        raise ValueError("Se esperaba true o false.")
    return normalized


def choice(value, options: tuple[str, ...]) -> str:
    normalized = str(value).strip().lower()
    if normalized not in options:
        raise ValueError(f"Opciones válidas: {', '.join(options)}.")
    return normalized


def text(value, max_length: int) -> str:
    value = str(value).strip()
    if len(value) > max_length or "\n" in value or "\r" in value:
        raise ValueError(f"Texto de hasta {max_length} caracteres, sin saltos de línea.")
    return value


def level_name(value) -> str:
    value = str(value).strip()
    if not _LEVEL_RE.fullmatch(value):
        raise ValueError("El nombre del mundo solo admite letras, números, guion bajo, espacio o guion.")
    return value


def ram_range(min_mb: int, max_mb: int) -> tuple[int, int]:
    min_mb, max_mb = int(min_mb), int(max_mb)
    if not 256 <= min_mb <= max_mb <= 65536:
        raise ValueError("La RAM debe cumplir 256 <= mínima <= máxima <= 65536 MB.")
    return min_mb, max_mb


def parse_mc_version(version: str) -> tuple[int, int, int] | None:
    """'1.20.4' -> (1, 20, 4). Versiones snapshot como '24w14a' -> None."""
    parts = version.split(".")
    if not 2 <= len(parts) <= 3 or not all(part.isdigit() for part in parts):
        return None
    numbers = [int(part) for part in parts] + [0] * (3 - len(parts))
    return numbers[0], numbers[1], numbers[2]


def ensure_inside(base: Path, target: Path) -> Path:
    """Impide operar fuera de la carpeta autorizada (por ejemplo, mediante '..')."""
    base_resolved, target_resolved = base.resolve(), target.resolve()
    if base_resolved not in target_resolved.parents:
        raise PermissionError(f"Ruta fuera de la carpeta autorizada: {target}")
    return target_resolved
