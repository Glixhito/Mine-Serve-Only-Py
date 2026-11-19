"""Advertencias de memoria y Java según la cantidad y el tamaño de los mods.

Son estimaciones para orientar, no garantías: el consumo real depende de cada mod.
"""
from __future__ import annotations

from dataclasses import dataclass

BASE_MB = 2048            # memoria base para un servidor con cargador
JAR_FACTOR = 2.5          # memoria extra estimada por cada MB de archivos .jar de mods
MANY_MODS = 100           # a partir de este número se avisa que el arranque será lento
MAX_RAM_CAP = 16384       # tope de la recomendación
JAVA_32BIT_LIMIT_MB = 1024
SYSTEM_SHARE = 0.75       # no conviene que el servidor use más de esta fracción de la RAM total
ORDER = {"error": 0, "aviso": 1, "info": 2}


@dataclass(frozen=True)
class Advice:
    level: str  # "error", "aviso" o "info"
    text: str


def suggested_max_ram(jar_mb: float) -> int:
    return min(MAX_RAM_CAP, BASE_MB + int(jar_mb * JAR_FACTOR))


def assess(*, mod_count: int, jar_mb: float, max_ram_mb: int, system_total_mb: int | None,
           java_present: bool, java_is_64bit: bool | None = None,
           java_compatible: bool | None = None, java_message: str = "") -> list[Advice]:
    advice: list[Advice] = []
    if not java_present:
        advice.append(Advice("error", "No hay Java válido seleccionado. Elígelo en Ajustes > Memoria y Java."))
    elif java_compatible is False:
        advice.append(Advice("error", java_message))
    if java_present and java_is_64bit is False and max_ram_mb > JAVA_32BIT_LIMIT_MB:
        advice.append(Advice("error", "La instalación de Java es de 32 bits y no puede usar más de 1 GB. "
                                      "Instala Java de 64 bits."))
    if system_total_mb and max_ram_mb > system_total_mb * SYSTEM_SHARE:
        advice.append(Advice("aviso", f"La RAM máxima ({max_ram_mb} MB) supera el 75% de la RAM de tu PC "
                                      f"({system_total_mb} MB). Windows y tu juego se quedarán sin memoria."))
    if mod_count > 0:
        suggested = suggested_max_ram(jar_mb)
        if max_ram_mb < suggested:
            advice.append(Advice("aviso", f"Con {mod_count} mods ({jar_mb:.0f} MB), conviene una RAM máxima de "
                                          f"al menos {suggested} MB. Tienes {max_ram_mb} MB; súbela en "
                                          "Ajustes > Memoria y Java."))
        if mod_count >= MANY_MODS:
            advice.append(Advice("info", f"Tienes {mod_count} mods. El primer arranque puede tardar varios minutos."))
    return sorted(advice, key=lambda item: ORDER[item.level])