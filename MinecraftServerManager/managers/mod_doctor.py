"""Arreglo automático de mods: actualiza los de Modrinth a la versión del servidor, instala dependencias
que falten y desactiva (sin borrar) los mods que no pueden funcionar. Todo se puede revertir."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from integrations.modrinth_api import ModrinthError
from managers.mod_manager import MODS_DIR, ModInfo, ModManager

MAX_PASSES = 5  # cada pasada instala o desactiva; con 5 basta para cadenas normales de dependencias


@dataclass
class FixReport:
    updated: list[str] = field(default_factory=list)    # "viejo.jar -> nuevo.jar"
    installed: list[str] = field(default_factory=list)  # archivos de dependencias instalados
    disabled: list[str] = field(default_factory=list)   # "archivo.jar: motivo"

    def lines(self) -> list[str]:
        out: list[str] = []
        if self.updated:
            out.append("Actualizados a tu versión de Minecraft: " + "; ".join(self.updated))
        if self.installed:
            out.append("Dependencias instaladas: " + ", ".join(self.installed))
        if self.disabled:
            out.append("Desactivados (no se borraron, puedes reactivarlos): " + "; ".join(self.disabled))
        if not out:
            out.append("Todos los mods activos son compatibles y tienen sus dependencias.")
        return out


class ModDoctor:
    def __init__(self, modrinth, manager: ModManager | None = None) -> None:
        self._modrinth = modrinth
        self._manager = manager or ModManager()
        self._attempted: set[str] = set()  # dependencias que ya se intentaron instalar en esta ejecución

    def run(self, server_dir: Path, minecraft_version: str, loader: str) -> FixReport:
        report = FixReport()
        self._attempted = set()
        self._update_incompatible(server_dir, minecraft_version, loader, report)
        for _ in range(MAX_PASSES):
            if not self._resolve_dependencies(server_dir, minecraft_version, loader, report):
                break
        return report

    def _active(self, server_dir: Path) -> list[ModInfo]:
        return [mod for mod in self._manager.list_mods(server_dir) if mod.enabled]

    def _update_incompatible(self, server_dir: Path, minecraft_version: str, loader: str,
                             report: FixReport) -> None:
        active = self._active(server_dir)
        versions = self._modrinth.installed_versions([mod.sha1 for mod in active])
        installed_ids = {version["project_id"] for version in versions.values()}
        for mod in active:
            version = versions.get(mod.sha1)
            if version is None:
                continue  # no es de Modrinth: no se puede comprobar su versión
            if minecraft_version in version.get("game_versions", []) and loader in version.get("loaders", []):
                continue
            try:
                plan = self._modrinth.plan_project(version["project_id"], minecraft_version, loader, installed_ids)
            except ModrinthError:
                self._disable(server_dir, mod, f"no tiene versión para Minecraft {minecraft_version} ({loader})",
                              report)
                continue
            if self._replace(server_dir, mod, plan, report):
                installed_ids |= {item["project_id"] for item in plan}

    def _replace(self, server_dir: Path, mod: ModInfo, plan: list[dict], report: FixReport) -> bool:
        """Mueve el mod viejo a mods_disabled y descarga la versión nueva; si la descarga falla, restaura el viejo."""
        try:
            self._manager.set_enabled(server_dir, mod.name, False, running=False)
        except OSError as error:
            report.disabled.append(f"{mod.name}: no se pudo reemplazar ({error})")
            return False
        try:
            paths = self._modrinth.download_plan(plan, server_dir / MODS_DIR)
        except Exception:
            self._manager.set_enabled(server_dir, mod.name, True, running=False)
            raise
        report.updated.append(f"{mod.name} -> {paths[0].name}")
        report.installed += [path.name for path in paths[1:]]
        return True

    def _resolve_dependencies(self, server_dir: Path, minecraft_version: str, loader: str,
                              report: FixReport) -> bool:
        """Una pasada: instala lo que falte y desactiva los mods con dependencias imposibles. True si cambió algo."""
        mods = self._manager.list_mods(server_dir)
        missing = self._manager.missing_dependencies(mods)
        if not missing:
            return False
        by_name = {mod.name: mod for mod in mods if mod.enabled}
        versions = self._modrinth.installed_versions([mod.sha1 for mod in by_name.values()])
        installed_ids = {version["project_id"] for version in versions.values()}
        previous = set(self._attempted)  # intentos de pasadas anteriores
        changed = False
        for name, dep_ids in sorted(missing.items()):
            mod = by_name[name]
            if dep_ids & previous:
                # Ya se instaló en una pasada anterior y sigue sin detectarse: no insistir.
                self._disable(server_dir, mod,
                              "faltan dependencias que ya se instalaron y no se detectan: "
                              + ", ".join(sorted(dep_ids)), report)
                changed = True
                continue
            self._attempted |= dep_ids
            plan, not_found = self._modrinth.plan_for_dependencies(
                sorted(dep_ids), minecraft_version, loader, installed_ids)
            if plan:
                paths = self._modrinth.download_plan(plan, server_dir / MODS_DIR)
                report.installed += [path.name for path in paths]
                installed_ids |= {item["project_id"] for item in plan}
                changed = True
            if not_found:
                self._disable(server_dir, mod, "faltan dependencias: " + "; ".join(not_found), report)
                changed = True
        return changed

    def _disable(self, server_dir: Path, mod: ModInfo, reason: str, report: FixReport) -> None:
        try:
            self._manager.set_enabled(server_dir, mod.name, False, running=False)
        except OSError as error:
            report.disabled.append(f"{mod.name}: no se pudo desactivar ({error})")
            return
        report.disabled.append(f"{mod.name}: {reason}")