"""Instala Java 25 (Eclipse Temurin) para el usuario, sin permisos de administrador.

Fuente: API oficial de Adoptium. El archivo se verifica con su SHA-256 antes de extraerlo.
"""
from __future__ import annotations

import hashlib
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlencode

from integrations import http_client

API = "https://api.adoptium.net/v3/assets/latest"
FEATURE = 25


class JavaInstallError(RuntimeError):
    pass


def asset_url(feature: int = FEATURE) -> str:
    query = urlencode({"os": "windows", "architecture": "x64", "image_type": "jdk", "vendor": "eclipse"})
    return f"{API}/{feature}/hotspot?{query}"


def pick_package(assets: list[dict]) -> tuple[str, str]:
    """Enlace y SHA-256 del primer paquete ZIP de la respuesta de Adoptium."""
    for asset in assets:
        package = asset.get("binary", {}).get("package", {})
        link, checksum = package.get("link", ""), package.get("checksum", "")
        if link.endswith(".zip") and len(checksum) == 64:
            return link, checksum.lower()
    raise JavaInstallError("Adoptium no devolvió un paquete ZIP de Java 25 para Windows x64.")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract(archive: Path, destination: Path) -> None:
    """Extrae el ZIP rechazando rutas que salgan de la carpeta de destino."""
    root = destination.resolve()
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            target = (destination / member.filename).resolve()
            if target != root and root not in target.parents:
                raise JavaInstallError(f"El paquete contiene una ruta no permitida: {member.filename}")
        zf.extractall(destination)


def find_java(root: Path) -> Path | None:
    return next(iter(sorted(root.rglob("bin/java.exe"))), None)


class JavaInstaller:
    def __init__(self, runtime_dir: Path, get_json=None, download=None) -> None:
        self._runtime = runtime_dir
        self._get_json = get_json or http_client.get_json
        self._download = download or http_client.download_file

    def _target(self) -> Path:
        return self._runtime / f"java-{FEATURE}"

    def installed_java(self) -> Path | None:
        target = self._target()
        return find_java(target) if target.is_dir() else None

    def install(self) -> Path:
        existing = self.installed_java()
        if existing:
            return existing
        link, expected = pick_package(self._get_json(asset_url()))
        self._runtime.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self._runtime) as tmp:
            archive = Path(tmp) / "java.zip"
            self._download(link, archive)
            if sha256_of(archive) != expected:
                raise JavaInstallError("El archivo descargado no coincide con su SHA-256. No se instaló.")
            staging = Path(tmp) / "extract"
            safe_extract(archive, staging)
            shutil.rmtree(self._target(), ignore_errors=True)
            shutil.move(str(staging), str(self._target()))
        java = self.installed_java()
        if java is None:
            raise JavaInstallError("El paquete de Java no contiene bin\\java.exe.")
        return java