"""Instalación de Java y ZeroTier, carpeta de datos y requisitos. Sin red y sin instalar nada."""
import zipfile
from pathlib import Path

import pytest

from managers import java_installer as ji
from managers import zerotier_installer as zt
from managers.java_manager import JavaInstall, JavaManager
from managers.setup_check import all_ok, evaluate
from utils import app_data


def _zip_with_java(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("jdk-25.0.5+1/bin/java.exe", b"fake")
        zf.writestr("jdk-25.0.5+1/release", b"JAVA_VERSION=25")


def _assets(checksum: str = "0" * 64) -> list[dict]:
    return [{"binary": {"package": {"link": "https://example.test/jdk.zip", "checksum": checksum}}}]


def test_asset_url_asks_for_windows_x64_jdk_25():
    url = ji.asset_url()
    assert "/assets/latest/25/hotspot" in url and "os=windows" in url and "architecture=x64" in url


def test_pick_package_requires_zip_with_sha256():
    assets = [{"binary": {"package": {"link": "https://x/a.tar.gz", "checksum": "a" * 64}}},
              {"binary": {"package": {"link": "https://x/b.zip", "checksum": "B" * 64}}}]
    assert ji.pick_package(assets) == ("https://x/b.zip", "b" * 64)


def test_pick_package_fails_without_zip():
    with pytest.raises(ji.JavaInstallError):
        ji.pick_package([])


def test_install_extracts_java_and_is_idempotent(tmp_path):
    source = tmp_path / "source.zip"
    _zip_with_java(source)
    installer = ji.JavaInstaller(
        tmp_path / "runtime",
        get_json=lambda url, *a, **k: _assets(ji.sha256_of(source)),
        download=lambda url, target: target.write_bytes(source.read_bytes()))
    java = installer.install()
    assert java.name == "java.exe" and java.is_file()
    assert installer.installed_java() == java
    assert installer.install() == java


def test_checksum_mismatch_installs_nothing(tmp_path):
    source = tmp_path / "source.zip"
    _zip_with_java(source)
    installer = ji.JavaInstaller(
        tmp_path / "runtime",
        get_json=lambda url, *a, **k: _assets("0" * 64),
        download=lambda url, target: target.write_bytes(source.read_bytes()))
    with pytest.raises(ji.JavaInstallError, match="SHA-256"):
        installer.install()
    assert installer.installed_java() is None


def test_zip_path_traversal_is_rejected(tmp_path):
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("../escape.txt", b"x")
    with pytest.raises(ji.JavaInstallError, match="no permitida"):
        ji.safe_extract(evil, tmp_path / "out")


def test_elevated_install_is_silent_and_asks_for_admin(tmp_path):
    text = " ".join(zt.elevated_install_command(tmp_path / "ZeroTierOne.msi"))
    assert "RunAs" in text and "/qn" in text and "/norestart" in text


def test_signature_check_escapes_apostrophes():
    assert "O''Brien" in " ".join(zt.signature_command(Path("C:/Users/O'Brien/x.msi")))


class _Result:
    def __init__(self, stdout: str = "", returncode: int = 0) -> None:
        self.stdout, self.returncode = stdout, returncode


def _responses(*items):
    queue, calls = list(items), []

    def run(command, **kwargs):
        calls.append(command)
        return queue.pop(0)
    return run, calls


def test_unsigned_installer_is_never_run(tmp_path):
    run, calls = _responses(_Result("NotSigned\n"))
    installer = zt.ZeroTierInstaller(tmp_path, download=lambda url, target: target.write_bytes(b"x"), run=run)
    with pytest.raises(zt.ZeroTierInstallError, match="firma"):
        installer.install()
    assert len(calls) == 1


def test_signed_installer_runs_elevated_install(tmp_path):
    run, calls = _responses(_Result("Valid\nCN=ZeroTier, Inc.\n"), _Result("", 0))
    installer = zt.ZeroTierInstaller(tmp_path, download=lambda url, target: target.write_bytes(b"x"), run=run)
    installer.install()
    assert len(calls) == 2 and "RunAs" in " ".join(calls[1])


def test_failed_zerotier_install_reports_exit_code(tmp_path):
    run, _ = _responses(_Result("Valid\nCN=ZeroTier, Inc.\n"), _Result("", 1603))
    installer = zt.ZeroTierInstaller(tmp_path, download=lambda url, target: target.write_bytes(b"x"), run=run)
    with pytest.raises(zt.ZeroTierInstallError, match="1603"):
        installer.install()


def test_requirements_block_start_until_java_and_zerotier_exist():
    reqs = evaluate(java_ok=False, zerotier_ok=True)
    assert [r.key for r in reqs] == ["java", "zerotier"]
    assert not all_ok(reqs) and reqs[1].ok
    assert all_ok(evaluate(True, True))


def test_user_data_dir_uses_local_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert app_data.user_data_dir() == tmp_path / "MinecraftServerManager"


def test_legacy_data_is_copied_once_and_never_overwritten(tmp_path):
    legacy = tmp_path / "old" / "data"
    (legacy / "servers").mkdir(parents=True)
    (legacy / "manager.db").write_text("db", encoding="utf-8")
    target = tmp_path / "new"
    target.mkdir()
    assert app_data.migrate_legacy(legacy, target) is True
    assert (target / "data" / "manager.db").read_text(encoding="utf-8") == "db"
    assert app_data.migrate_legacy(legacy, target) is False


def test_java_from_runtime_folder_is_detected(tmp_path, monkeypatch):
    exe = tmp_path / "java-25" / "bin" / "java.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"x")
    manager = JavaManager(extra_roots=(tmp_path,))
    monkeypatch.setattr(manager, "probe", lambda path: JavaInstall(path=path, major=25, raw_version="25"))
    assert any(install.path.endswith("java.exe") for install in manager.detect())