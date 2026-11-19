"""Verifica que la estructura esté completa y que los módulos importen.

Uso, desde la carpeta del proyecto (MinecraftServerManager) con el entorno activo:
    python verificar.py
"""
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARCHIVOS = """
main.py verificar.py build.ps1 requirements.txt pytest.ini README.md .gitignore
core/__init__.py core/application.py core/event_manager.py core/process_manager.py core/server_controller.py
database/__init__.py database/connection.py database/models.py
integrations/__init__.py integrations/http_client.py integrations/minecraft_api.py
integrations/loader_base.py integrations/fabric_installer.py integrations/forge_installer.py
integrations/neoforge_installer.py integrations/modrinth_api.py
managers/__init__.py managers/backup_manager.py managers/config_manager.py managers/java_manager.py
managers/loader_manager.py managers/log_manager.py managers/mod_manager.py managers/player_admin.py
managers/player_tracker.py managers/server_manager.py managers/server_monitor.py managers/version_manager.py
repositories/__init__.py repositories/server_repository.py repositories/operation_repository.py
ui/__init__.py ui/create_server_dialog.py ui/dashboard.py ui/history_view.py ui/main_window.py
ui/mod_view.py ui/players_view.py ui/server_view.py ui/settings_view.py ui/workers.py
ui/widgets/__init__.py ui/widgets/placeholder.py
utils/__init__.py utils/file_manager.py utils/network.py utils/system_info.py utils/validators.py
tests/test_basics.py tests/test_phase2.py tests/test_phase34.py tests/test_players.py tests/test_phase4_actions.py
""".split()

faltan = [archivo for archivo in ARCHIVOS if not (ROOT / archivo).is_file()]
if faltan:
    print("Faltan estos archivos:")
    for archivo in faltan:
        print("  -", archivo)
    sys.exit(1)

sys.path.insert(0, str(ROOT))
modulos = [archivo[:-3].replace("/", ".") for archivo in ARCHIVOS
           if archivo.endswith(".py")
           and archivo not in ("main.py", "verificar.py")
           and not archivo.endswith("__init__.py")
           and not archivo.startswith("tests/")]
errores = []
for nombre in modulos:
    try:
        importlib.import_module(nombre)
    except Exception as error:
        errores.append(f"{nombre}: {type(error).__name__}: {error}")

if errores:
    print("Errores de importación:")
    for linea in errores:
        print("  -", linea)
    sys.exit(1)
print(f"OK: {len(ARCHIVOS)} archivos presentes; {len(modulos)} módulos importan correctamente.")