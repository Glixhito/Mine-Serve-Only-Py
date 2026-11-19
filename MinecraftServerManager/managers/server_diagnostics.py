"""Diagnóstico del servidor: lee el último arranque (logs/latest.log) y el último crash report.

Responde: ¿cargaron los mods activos?, ¿terminó el arranque?, ¿hubo errores al generar el mundo?
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from managers.log_manager import server_log_file

PREFIX_RE = re.compile(r"^\[[^\]]*\]\s*\[[^\]]*\]:\s?")  # "[12:00:00] [Server thread/INFO]: "
ERROR_LEVEL_RE = re.compile(r"/(ERROR|FATAL)\]")
LOADING_RE = re.compile(r"Loading \d+ mods?:")          # Fabric: lista de mods al arrancar
MOD_LINE_RE = re.compile(r"^\s*-\s+(\S+)\s+\S+")         # Fabric: "\t- geophilic 3.7"
NESTED_RE = re.compile(r"^\s+[|\\ ]*[|\\]--")   # Fabric: "\t   \-- mixinextras 0.5.5"
DONE_RE = re.compile(r"Done \(([\d.]+)s\)!")
SPAWN_RE = re.compile(r"Preparing spawn area: (\d+)%")
WORLDGEN_MARKERS = ("generating new chunk", "generating chunk", "Couldn't place", "Failed to generate")


def _preview(items: list[str], limit: int = 3) -> str:
    shown = " | ".join(items[:limit])
    return shown + (f" (y {len(items) - limit} más)" if len(items) > limit else "")


@dataclass
class Diagnosis:
    has_log: bool = False
    startup_seconds: float | None = None
    loaded_mods: list[str] = field(default_factory=list)
    expected_count: int = 0
    missing_mods: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    worldgen_problems: list[str] = field(default_factory=list)
    spawn_percent: int | None = None
    crash: str | None = None

    def problems(self) -> list[str]:
        out = []
        if self.startup_seconds is None:
            out.append("• El servidor no terminó de arrancar.")
        if self.missing_mods:
            out.append("• Mods activos que no cargaron: " + ", ".join(self.missing_mods))
        if self.crash:
            out.append(f"• Último crash: {self.crash}")
        if self.worldgen_problems:
            out.append(f"• Problemas al generar el mundo ({len(self.worldgen_problems)}): "
                       + _preview(self.worldgen_problems))
        if self.errors:
            out.append(f"• Errores en el log ({len(self.errors)}): " + _preview(self.errors))
        return out

    def lines(self) -> list[str]:
        if not self.has_log:
            return ["No hay registro del servidor. Inícialo al menos una vez y vuelve a revisar."]
        problems = self.problems()
        out = ["Resultado: hay problemas que revisar." if problems else "Resultado: todo parece correcto."]
        out += problems
        if self.startup_seconds is not None:
            out.append(f"Arranque completado en {self.startup_seconds:.1f} s.")
        if self.loaded_mods:
            out.append(f"Mods cargados según el log ({len(self.loaded_mods)}): {', '.join(self.loaded_mods)}")
        elif self.expected_count:
            out.append("No encontré la lista de mods en el log, así que no puedo confirmar cuáles cargaron.")
        if self.spawn_percent is not None:
            out.append(f"Última preparación de la zona de aparición: {self.spawn_percent}%.")
        return out

def parse_log(text: str) -> Diagnosis:
    diagnosis = Diagnosis(has_log=True)
    in_mod_list = False
    for raw in text.splitlines():
        message = PREFIX_RE.sub("", raw)
        if LOADING_RE.search(message):
            in_mod_list = True
            continue
        if in_mod_list:
            match = MOD_LINE_RE.match(message)
            if match:
                diagnosis.loaded_mods.append(match.group(1))
                continue
            if NESTED_RE.match(message):  # dependencias internas: no cortan la lista
                continue
            in_mod_list = False
        done = DONE_RE.search(message)
        if done:
            diagnosis.startup_seconds = float(done.group(1))
        spawn = SPAWN_RE.search(message)
        if spawn:
            diagnosis.spawn_percent = int(spawn.group(1))
        if ERROR_LEVEL_RE.search(raw):
            target = diagnosis.worldgen_problems if any(m in message for m in WORLDGEN_MARKERS) else diagnosis.errors
            if message not in target:
                target.append(message)
    return diagnosis

def latest_crash(server_dir: Path) -> str | None:
    crash_dir = server_dir / "crash-reports"
    if not crash_dir.is_dir():
        return None
    reports = sorted(crash_dir.glob("crash-*.txt"), key=lambda path: path.stat().st_mtime)
    if not reports:
        return None
    newest = reports[-1]
    description, cause = "sin descripción", ""
    for line in newest.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if line.startswith("Description:") and description == "sin descripción":
            description = line.removeprefix("Description:").strip()
        elif stripped.startswith("Caused by:") and not cause:
            cause = stripped.removeprefix("Caused by:").strip()
    text = f"{newest.name}: {description}"
    return f"{text} (causa: {cause})" if cause else text


def diagnose(server_dir: Path, expected_mod_ids: set[str] | frozenset[str] = frozenset()) -> Diagnosis:
    log = server_log_file(server_dir)
    if log.is_file():
        diagnosis = parse_log(log.read_text(encoding="utf-8", errors="replace"))
    else:
        diagnosis = Diagnosis(has_log=False)
    diagnosis.expected_count = len(expected_mod_ids)
    if diagnosis.loaded_mods and expected_mod_ids:
        diagnosis.missing_mods = sorted(set(expected_mod_ids) - set(diagnosis.loaded_mods))
    diagnosis.crash = latest_crash(server_dir)
    return diagnosis