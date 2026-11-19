"""Base común para cargadores con instalador oficial (Forge y NeoForge): --installServer."""
from __future__ import annotations

import os
import subprocess
import zipfile
from pathlib import Path

from integrations import http_client

INSTALL_TIMEOUT_S = 900
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class LoaderError(RuntimeError):
    """Fallo al instalar un cargador. El mensaje está pensado para el usuario."""


def _remote_sha1(url: str) -> str | None:
    """Maven publica un .sha1 junto a cada archivo; si existe, la verificación es obligatoria."""
    text = http_client.get_text_or_none(url + ".sha1")
    return text.split()[0] if text else None


class InstallerLoader:
    loader = ""
    needs_java = True

    def installer_url(self, minecraft_version: str, loader_version: str) -> str:
        raise NotImplementedError

    def argfile_dir(self, minecraft_version: str, loader_version: str) -> str:
        raise NotImplementedError

    def install(self, server_dir: Path, minecraft_version: str, loader_version: str, java_path: str) -> dict:
        url = self.installer_url(minecraft_version, loader_version)
        jar = server_dir / f"{self.loader}-installer.jar"
        http_client.download_file(url, jar, expected_sha1=_remote_sha1(url))
        try:
            if not zipfile.is_zipfile(jar):
                raise LoaderError("El instalador descargado no es un JAR válido.")
            result = subprocess.run(
                [java_path, "-jar", jar.name, "--installServer"],
                cwd=server_dir, capture_output=True, encoding="utf-8", errors="replace",
                timeout=INSTALL_TIMEOUT_S, check=False, creationflags=_NO_WINDOW,
            )
        finally:
            jar.unlink(missing_ok=True)
        if result.returncode != 0:
            tail = "\n".join(result.stdout.splitlines()[-15:])
            raise LoaderError(f"El instalador de {self.loader} falló:\n{tail}")
        suffix = "win_args.txt" if os.name == "nt" else "unix_args.txt"
        target = f"{self.argfile_dir(minecraft_version, loader_version)}/{suffix}"
        if not (server_dir / target).is_file():
            raise LoaderError("El instalador no generó el archivo de argumentos esperado.")
        return {"mode": "argfile", "target": target}
