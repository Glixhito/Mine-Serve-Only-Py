"""Lógica de negocio de servidores: crear, consultar, instalar Vanilla, configurar y eliminar."""
from __future__ import annotations
from managers.config_manager import RULES, ConfigManager
import logging
import shutil
from pathlib import Path

from database.models import ServerRecord
from managers.config_manager import ConfigManager
from managers.version_manager import VersionManager
from repositories.server_repository import ServerRepository
from utils import file_manager, validators
from utils.network import port_is_free

log = logging.getLogger(__name__)
SERVER_JAR = "server.jar"


class ServerManager:
    def __init__(self, repository: ServerRepository, servers_dir: Path,
                 versions: VersionManager, config: ConfigManager) -> None:
        self._repo = repository
        self._servers_dir = servers_dir
        self._versions = versions
        self._config = config
        self.on_created = None  # gancho opcional: lo usa ZeroTier para crear la red        

    def list_servers(self) -> list[ServerRecord]:
        return self._repo.list_all()

    def get(self, server_id: int) -> ServerRecord:
        record = self._repo.get(server_id)
        if record is None:
            raise KeyError(f"No existe un servidor con id {server_id}.")
        return record

    def create(self, name: str, minecraft_version: str, *, description: str = "",
               min_ram: int = 1024, max_ram: int = 2048, online_mode: bool = True) -> ServerRecord:
        """Crea carpeta, server.properties y registro. El jar se descarga con install_vanilla."""
        name = validators.server_name(name)
        min_ram, max_ram = validators.ram_range(min_ram, max_ram)
        if validators.parse_mc_version(minecraft_version) is None:
            raise ValueError(f"Versión de Minecraft no válida: {minecraft_version}")
        folder = self._servers_dir / file_manager.slugify(name)
        if folder.exists():
            raise FileExistsError(f"Ya existe una carpeta para '{name}'; no se sobrescribe.")
        folder.mkdir(parents=True)
        try:
            self._config.create_default(folder, online_mode=online_mode)
            self._config.write(folder, {"server-port": str(self.allocate_port())})
            record = self._repo.insert(ServerRecord(
                name=name, description=description, minecraft_version=minecraft_version,
                server_path=str(folder.resolve()), min_ram=min_ram, max_ram=max_ram,
                online_mode=online_mode,
            ))
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)  # no dejar carpetas huérfanas
            raise
        if self.on_created is not None:
            try:
                self.on_created(record)
            except Exception as error:  # la red ZeroTier es opcional: no impide crear el servidor
                log.warning("Red ZeroTier no creada: %s", error)        
        log.info("Servidor creado: %s (%s)", name, minecraft_version)
        return record

    def install_vanilla(self, server_id: int) -> Path:
        """Descarga server.jar oficial y verifica su SHA-1. No sobrescribe un jar existente."""
        record = self.get(server_id)
        target = Path(record.server_path) / SERVER_JAR
        if target.exists():
            raise FileExistsError("server.jar ya existe; no se reemplaza sin autorización.")
        return self._versions.download_server_jar(record.minecraft_version, target)

    def update_runtime(self, server_id: int, *, java_path: str, min_ram: int, max_ram: int) -> ServerRecord:
        record = self.get(server_id)
        min_ram, max_ram = validators.ram_range(min_ram, max_ram)
        record.java_path, record.min_ram, record.max_ram = java_path, min_ram, max_ram
        self._repo.update(record)
        return record

    def set_online_mode(self, server_id: int, online: bool, *, acknowledged_risk: bool = False) -> None:
        """Cambia online-mode. El modo offline exige confirmar antes la advertencia de seguridad."""
        if not online and not acknowledged_risk:
            raise PermissionError("El modo offline permite suplantar nombres de usuario; confirma la advertencia.")
        record = self.get(server_id)
        self._config.write(Path(record.server_path), {"online-mode": "true" if online else "false"})
        record.online_mode = online
        self._repo.update(record)

    def set_loader(self, server_id: int, server_type: str, loader_version: str | None) -> ServerRecord:
        record = self.get(server_id)
        record.server_type, record.loader_version = server_type, loader_version
        self._repo.update(record)
        return record

    def edit(self, server_id: int, *, name: str | None = None, description: str | None = None) -> ServerRecord:
        """Cambia el nombre (único en la base de datos) y la descripción. La carpeta no cambia."""
        record = self.get(server_id)
        if name is not None:
            name = validators.server_name(name)
            if any(other.name == name and other.id != server_id for other in self._repo.list_all()):
                raise ValueError(f"Ya existe un servidor llamado «{name}».")
            record.name = name
        if description is not None:
            record.description = description.strip()[:200]
        self._repo.update(record)
        return record

    def copy_settings(self, source_id: int, target_id: int) -> None:
        """Copia la configuración de server.properties y online-mode, sin el mundo ni los jar."""
        source = self.get(source_id)
        target = self.get(target_id)
        props = {key: value for key, value in self._config.read(Path(source.server_path)).items()
                 if key in RULES and key != "server-port"}
        self._config.write(Path(target.server_path), props)
        self._config.write(Path(target.server_path), {"server-port": str(self.allocate_port())})
        target.online_mode = source.online_mode
        self._repo.update(target)

    def set_world(self, server_id: int, seed: str, level_type: str) -> None:
        """Define la semilla y el tipo de mundo. Solo aplica mientras el mundo todavía no existe."""
        record = self.get(server_id)
        folder = Path(record.server_path)
        level_name = self._config.read(folder).get("level-name", "world")
        if (folder / level_name).exists():
            raise ValueError("El mundo ya existe; la semilla solo se aplica a un mundo nuevo.")
        self._config.write(folder, {"level-seed": seed.strip(), "level-type": level_type})

    def allocate_port(self, start: int = 25565, end: int = 25699) -> int:
        """Primer puerto libre: no lo usa otro programa ni lo tiene asignado otro servidor."""
        reserved = set()
        for record in self._repo.list_all():
            try:
                reserved.add(int(self._config.read(Path(record.server_path)).get("server-port", "25565")))
            except ValueError:
                pass
        for port in range(start, end + 1):
            if port not in reserved and port_is_free(port):
                return port
        raise RuntimeError(f"No hay puertos libres entre {start} y {end}.")

    def delete(self, server_id: int, *, confirmed: bool) -> None:
        """Elimina registro y carpeta. Requiere confirmación explícita.
        TODO (Fase 4): crear un respaldo antes de borrar."""
        if not confirmed:
            raise PermissionError("Eliminar un servidor requiere confirmación explícita.")
        record = self.get(server_id)
        folder = validators.ensure_inside(self._servers_dir, Path(record.server_path))
        self._repo.delete(server_id)
        shutil.rmtree(folder)
        log.warning("Servidor eliminado: %s", record.name)
