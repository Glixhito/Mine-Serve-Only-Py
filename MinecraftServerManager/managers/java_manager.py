"""Detección y validación de Java. Nunca descarga ni instala Java automáticamente."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from glob import glob
from pathlib import Path

from utils.validators import parse_mc_version

_VERSION_RE = re.compile(r'version \"(\d+)(?:\.(\d+))?')
_EXE = "java.exe" if os.name == "nt" else "java"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass(frozen=True)
class JavaInstall:
    path: str
    major: int
    raw_version: str
    is_64bit: bool = True


def required_java_major(mc_version: str) -> int | None:
    """Java mínimo según la versión de Minecraft. Confirmar estos umbrales en la documentación oficial."""
    parsed = parse_mc_version(mc_version)
    if parsed is None:
        return None
    if parsed >= (26, 0, 0):
        return 25  # Minecraft 26.x se compila para Java 25
    if parsed < (1, 17, 0):
        return 8
    if parsed < (1, 18, 0):
        return 16
    if parsed < (1, 20, 5):
        return 17
    return 21


class JavaManager:
    def __init__(self, extra_roots: tuple = ()) -> None:
        self._extra_roots = [Path(root) for root in extra_roots]  # p. ej. la carpeta del Java instalado por la app
        # Ruta -> (tamaño, fecha de modificación) y resultado. Solo se guardan los resultados válidos.
        self._probe_cache: dict[str, tuple[tuple[int, int], JavaInstall]] = {}

    def probe(self, path: str) -> JavaInstall | None:
        """Instalación de Java en esa ruta. El resultado se reutiliza mientras el ejecutable no cambie."""
        exe = Path(path)
        if not exe.is_file():
            return None
        stat = exe.stat()
        signature = (stat.st_size, stat.st_mtime_ns)
        cached = self._probe_cache.get(str(exe))
        if cached and cached[0] == signature:
            return cached[1]
        install = self._run_version(exe)
        if install is not None:
            self._probe_cache[str(exe)] = (signature, install)
        return install

    def _run_version(self, exe: Path) -> JavaInstall | None:
        """Ejecuta 'java -version' sin shell y devuelve la instalación, o None si no es válida."""
        try:
            result = subprocess.run(
                [str(exe), "-version"], capture_output=True, encoding="utf-8",
                errors="replace", timeout=15, check=False, creationflags=_NO_WINDOW,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        output = result.stderr or result.stdout  # java escribe la versión en stderr
        match = _VERSION_RE.search(output)
        if match is None:
            return None
        first, second = int(match.group(1)), match.group(2)
        major = int(second) if first == 1 and second else first  # "1.8.0" -> 8
        return JavaInstall(path=str(exe), major=major, raw_version=output.splitlines()[0],
                           is_64bit="64-Bit" in output)

    def detect(self) -> list[JavaInstall]:
        """Busca Java en la carpeta de la app, JAVA_HOME, el PATH y rutas habituales de Windows."""
        candidates: list[str] = []
        for root in self._extra_roots:
            if root.is_dir():
                candidates += [str(path) for path in sorted(root.rglob("bin/java.exe"))]
        if java_home := os.environ.get("JAVA_HOME"):
            candidates.append(str(Path(java_home) / "bin" / _EXE))
        if found := shutil.which("java"):
            candidates.append(found)
        if os.name == "nt":
            candidates += glob(r"C:\Program Files\Java\*\bin\java.exe")
            candidates += glob(r"C:\Program Files\Eclipse Adoptium\*\bin\java.exe")
        installs: list[JavaInstall] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = str(Path(candidate).resolve())
            if key in seen:
                continue
            seen.add(key)
            install = self.probe(candidate)
            if install is not None:
                installs.append(install)
        return installs

    def check_compatibility(self, install: JavaInstall, mc_version: str) -> tuple[bool, str]:
        needed = required_java_major(mc_version)
        if needed is None:
            return False, f"No se pudo determinar la versión de Java para Minecraft {mc_version}."
        if install.major < needed:
            return False, (f"Minecraft {mc_version} requiere Java {needed} o superior "
                           f"(detectado: Java {install.major}).")
        return True, "Compatible."