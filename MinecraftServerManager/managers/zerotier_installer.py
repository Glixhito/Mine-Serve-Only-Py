"""ZeroTier One para Windows: descarga el instalador oficial, comprueba su firma y lo instala con permiso de administrador."""
from __future__ import annotations

import subprocess
from pathlib import Path

from integrations import http_client
from integrations.zerotier_local import CANDIDATES

MSI_URL = "https://download.zerotier.com/dist/ZeroTier%20One.msi"
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ZeroTierInstallError(RuntimeError):
    pass


def _powershell(script: str) -> list[str]:
    return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]


def _quote(path: Path) -> str:
    return str(path).replace("'", "''")


def signature_command(msi: Path) -> list[str]:
    return _powershell(f"$s = Get-AuthenticodeSignature -LiteralPath '{_quote(msi)}'; "
                       "Write-Output $s.Status; Write-Output $s.SignerCertificate.Subject")


def elevated_install_command(msi: Path) -> list[str]:
    arguments = f"'/i', '\"{_quote(msi)}\"', '/qn', '/norestart'"
    return _powershell("$p = Start-Process -FilePath msiexec.exe -Verb RunAs -Wait -PassThru "
                       f"-ArgumentList @({arguments}); exit $p.ExitCode")


class ZeroTierInstaller:
    def __init__(self, cache_dir: Path, download=None, run=None) -> None:
        self._cache = cache_dir
        self._download = download or http_client.download_file
        self._run = run or subprocess.run

    def is_installed(self) -> bool:
        return any(Path(candidate).is_file() for candidate in CANDIDATES)

    def is_signed_by_zerotier(self, msi: Path) -> bool:
        result = self._run(signature_command(msi), capture_output=True, text=True,
                           creationflags=_NO_WINDOW, check=False)
        lines = result.stdout.strip().splitlines()
        return len(lines) >= 2 and lines[0].strip() == "Valid" and "ZeroTier" in lines[1]

    def install(self) -> None:
        self._cache.mkdir(parents=True, exist_ok=True)
        msi = self._cache / "ZeroTierOne.msi"
        self._download(MSI_URL, msi)
        if not self.is_signed_by_zerotier(msi):
            raise ZeroTierInstallError("El instalador descargado no tiene la firma de ZeroTier. No se instaló.")
        result = self._run(elevated_install_command(msi), capture_output=True, text=True,
                           creationflags=_NO_WINDOW, check=False)
        if result.returncode != 0:
            raise ZeroTierInstallError(f"La instalación terminó con código {result.returncode}. "
                                       "Si cerraste la ventana de permisos, vuelve a intentarlo.")