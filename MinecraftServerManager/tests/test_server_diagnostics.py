"""Diagnóstico del servidor a partir de logs reales y de ejemplo. Sin servidor ni red."""
from pathlib import Path

from managers.server_diagnostics import diagnose, parse_log

# Formato real de Fabric: la lista de mods es un solo mensaje con saltos de línea.
# Solo la primera línea lleva prefijo; las líneas anidadas son dependencias internas.
REAL_LIST_LOG = (
    "[13:29:10] [main/INFO]: Loading 49 mods:\n"
    "\t- apollib 1.2.4\n"
    "\t   \\-- de_marhali_json5-java 3.0.0\n"
    "\t- fabric-api 0.165.2+26.3\n"
    "\t   |-- fabric-api-base 2.0.6+fcdff87f5d\n"
    "\t   \\-- fabric-transitive-access-wideners-v1 8.1.17+e2f63d3e5d\n"
    "\t- fabricloader 0.20.1\n"
    "\t   \\-- mixinextras 0.5.5\n"
    "\t- geophilic 3.7\n"
    "[13:29:10] [main/INFO]: SpongePowered MIXIN Subsystem Version=0.8.7\n"
    "[13:29:20] [Server thread/INFO]: Preparing spawn area: 0%\n"
    "[13:29:20] [Server thread/INFO]: Preparing spawn area: 100%\n"
    "[13:29:20] [Server thread/INFO]: Done (0.538s)! For help, type \"help\"\n"
)


def _write_log(server_dir: Path, text: str) -> None:
    (server_dir / "logs").mkdir(parents=True, exist_ok=True)
    (server_dir / "logs" / "latest.log").write_text(text, encoding="utf-8")


def test_real_fabric_log_lists_top_level_mods_and_startup():
    diagnosis = parse_log(REAL_LIST_LOG)
    assert diagnosis.loaded_mods == ["apollib", "fabric-api", "fabricloader", "geophilic"]
    assert diagnosis.startup_seconds == 0.538
    assert diagnosis.spawn_percent == 100
    assert diagnosis.problems() == []
    assert diagnosis.lines()[0] == "Resultado: todo parece correcto."


def test_worldgen_error_is_reported_separately_from_other_errors():
    log = REAL_LIST_LOG + "[13:30:00] [Server thread/ERROR]: Exception generating new chunk at 10 20\n" \
                          "[13:30:01] [Server thread/ERROR]: Algo más falló\n"
    diagnosis = parse_log(log)
    assert diagnosis.worldgen_problems == ["Exception generating new chunk at 10 20"]
    assert diagnosis.errors == ["Algo más falló"]
    assert diagnosis.lines()[0] == "Resultado: hay problemas que revisar."


def test_missing_active_mod_is_detected(tmp_path):
    _write_log(tmp_path, REAL_LIST_LOG)
    diagnosis = diagnose(tmp_path, {"geophilic", "epic"})
    assert diagnosis.missing_mods == ["epic"]
    assert any("epic" in line for line in diagnosis.problems())


def test_expected_mods_found_are_not_reported_missing(tmp_path):
    _write_log(tmp_path, REAL_LIST_LOG)
    diagnosis = diagnose(tmp_path, {"apollib", "fabric-api", "geophilic"})
    assert diagnosis.missing_mods == []


def test_unfinished_startup_is_a_problem(tmp_path):
    _write_log(tmp_path, REAL_LIST_LOG.replace("Done (0.538s)! For help, type \"help\"\n", ""))
    diagnosis = diagnose(tmp_path)
    assert diagnosis.startup_seconds is None
    assert any("no terminó" in line for line in diagnosis.problems())


def test_missing_log_asks_to_start_server(tmp_path):
    diagnosis = diagnose(tmp_path, {"geophilic"})
    assert diagnosis.has_log is False
    assert "No hay registro" in diagnosis.lines()[0]


def test_crash_report_is_summarized(tmp_path):
    crash_dir = tmp_path / "crash-reports"
    crash_dir.mkdir()
    (crash_dir / "crash-2026-11-09_12.00.00-server.txt").write_text(
        "---- Minecraft Crash Report ----\nDescription: Mod crashed\n\n"
        "java.lang.IllegalStateException: boom\nCaused by: java.lang.NullPointerException: x\n",
        encoding="utf-8")
    diagnosis = diagnose(tmp_path)
    assert "Mod crashed" in diagnosis.crash
    assert "NullPointerException" in diagnosis.crash


def test_forge_log_without_mod_list_does_not_claim_missing_mods(tmp_path):
    _write_log(tmp_path, REAL_LIST_LOG.replace("Loading 49 mods:", "Loading minecraft"))
    diagnosis = diagnose(tmp_path, {"geophilic"})
    assert diagnosis.missing_mods == []
    assert any("no puedo confirmar" in line for line in diagnosis.lines())