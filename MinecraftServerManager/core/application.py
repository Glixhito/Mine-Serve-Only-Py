"""Composición de la aplicación: crea los servicios una sola vez y los comparte."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.event_manager import EventManager
from core.server_controller import ServerController
from database.connection import Database
from integrations import http_client
from integrations.modrinth_api import ModrinthClient
from managers.backup_manager import BackupManager
from managers.backup_policy import BackupPolicyStore
from managers.config_manager import ConfigManager
from managers.java_manager import JavaManager
from managers.loader_manager import LoaderManager
from managers.loader_catalog import LoaderCatalog
from managers.log_manager import setup_logging
from managers.mod_manager import ModManager
from managers.player_admin import PlayerAdmin
from managers.player_tracker import PlayerTracker
from managers.presets import PresetManager
from managers.server_manager import ServerManager
from managers.server_monitor import ServerMonitor
from managers.version_manager import VersionManager
from managers.welcome_messenger import WelcomeMessenger
from managers.performance_monitor import PerformanceMonitor
from managers.whitelist_manager import WhitelistManager
from managers.zerotier_manager import ZeroTierManager
from repositories.operation_repository import OperationRepository
from repositories.server_repository import ServerRepository
from repositories.settings_repository import SettingsRepository


@dataclass(frozen=True)
class AppPaths:
    """Rutas de datos, dentro de la carpeta del proyecto (data/)."""

    base: Path

    @property
    def data(self) -> Path:
        return self.base / "data"

    @property
    def servers(self) -> Path:
        return self.data / "servers"

    @property
    def backups(self) -> Path:
        return self.data / "backups"

    @property
    def logs(self) -> Path:
        return self.data / "logs"

    @property
    def cache(self) -> Path:
        return self.data / "cache"

    @property
    def database(self) -> Path:
        return self.data / "manager.db"

    def ensure(self) -> None:
        for folder in (self.servers, self.backups, self.logs, self.cache):
            folder.mkdir(parents=True, exist_ok=True)


class Application:
    def __init__(self, base_dir: Path) -> None:
        self.paths = AppPaths(Path(base_dir))
        self.paths.ensure()
        setup_logging(self.paths.logs)

        self.db = Database(self.paths.database)
        self.db.init_schema()

        self.events = EventManager()
        self.java = JavaManager(extra_roots=(self.paths.base / "runtime",))
        self.config = ConfigManager()
        self.versions = VersionManager(self.paths.cache)
        self.servers = ServerManager(
            repository=ServerRepository(self.db),
            servers_dir=self.paths.servers,
            versions=self.versions,
            config=self.config,
        )
        self.loaders = LoaderManager(self.servers, self.java, self.paths.cache)
        self.loader_catalog = LoaderCatalog(self.paths.cache)  
        self.mods = ModManager()
        self.modrinth = ModrinthClient(self.paths.cache)
        self.controller = ServerController(
            servers=self.servers, config=self.config, java=self.java, events=self.events,
        )
        self.operations = OperationRepository(self.db)
        self.settings = SettingsRepository(self.db)
        self.policies = BackupPolicyStore(self.settings)
        self.backups = BackupManager(self.paths.backups)
        self.presets = PresetManager(self.servers, self.config, self.backups, self.operations)
        self.whitelist = WhitelistManager()
        self.players = PlayerAdmin(self.controller, self.operations, self.servers, self.whitelist)
        self.monitor = ServerMonitor()
        self.welcome = WelcomeMessenger(self.events, self.controller)
        self.performance = PerformanceMonitor(self.events)
        self.tracker = PlayerTracker(self.events)
        self.zerotier = ZeroTierManager(self.settings, self.servers, self.operations, self.events, self.config)
        self.servers.on_created = self.zerotier.provision

    def close(self) -> None:
        """Detiene los servidores de forma ordenada, cierra la base de datos y las conexiones HTTP."""
        self.controller.shutdown()
        self.db.close()
        http_client.close()