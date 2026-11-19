"""Requisitos de la app: Java 25 y ZeroTier. Lógica pura, sin interfaz."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Requirement:
    key: str
    title: str
    ok: bool
    detail: str


def evaluate(java_ok: bool, zerotier_ok: bool) -> list[Requirement]:
    return [
        Requirement("java", "Java 25", java_ok,
                    "Instalado." if java_ok else "Falta. La app puede instalarlo por ti."),
        Requirement("zerotier", "ZeroTier", zerotier_ok,
                    "Instalado." if zerotier_ok else
                    "Falta. La app puede instalarlo por ti; Windows pedirá permiso de administrador."),
    ]


def all_ok(requirements: list[Requirement]) -> bool:
    return all(item.ok for item in requirements)