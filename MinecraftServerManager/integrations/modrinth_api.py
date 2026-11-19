"""Cliente de Modrinth: búsqueda, dependencias obligatorias, lado cliente/servidor y descargas por lotes.

Verificar los endpoints y campos en la documentación oficial de Modrinth antes de producción.
"""
from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from integrations import http_client
from utils import validators

BASE_URL = "https://api.modrinth.com/v2"
BATCH = 100  # tamaño máximo por petición en lote


class ModrinthError(RuntimeError):
    """Mod sin versión compatible o archivo no permitido."""


class ModrinthClient:
    def __init__(self, cache_dir: Path) -> None:
        self._cache = cache_dir
        self._project_versions: dict[tuple[str, str, str], list[dict]] = {}  # memoria de sesión
        # SHA-1 -> versión de Modrinth, o None si Modrinth no reconoce el archivo. Dura lo que la sesión.
        self._file_versions: dict[str, dict | None] = {}

    def search(self, query: str, minecraft_version: str, loader: str, limit: int = 20) -> list[dict]:
        """Mods compatibles con la versión y el cargador. Se omiten los que no funcionan en servidor."""
        facets = [["project_type:mod"], [f"versions:{minecraft_version}"], [f"categories:{loader}"]]
        data = http_client.get_json(f"{BASE_URL}/search", self._cache,
                                    params={"query": query, "facets": json.dumps(facets), "limit": limit})
        return [hit for hit in data["hits"] if hit.get("server_side") != "unsupported"]

    def project_versions(self, project_id: str, minecraft_version: str, loader: str) -> list[dict]:
        key = (project_id, minecraft_version, loader)
        if key not in self._project_versions:
            params = {"loaders": json.dumps([loader]), "game_versions": json.dumps([minecraft_version])}
            self._project_versions[key] = http_client.get_json(
                f"{BASE_URL}/project/{project_id}/version", self._cache, params=params)
        return self._project_versions[key]

    def _versions_by_hash(self, sha1_list: list[str]) -> dict[str, dict]:
        """SHA-1 -> versión de Modrinth. Solo pregunta los archivos que aún no están en memoria."""
        unknown = [sha1 for sha1 in dict.fromkeys(sha1_list) if sha1 not in self._file_versions]
        for start in range(0, len(unknown), BATCH):
            batch = unknown[start:start + BATCH]
            response = http_client.client().post(
                f"{BASE_URL}/version_files", json={"hashes": batch, "algorithm": "sha1"})
            response.raise_for_status()
            found = response.json()
            for sha1 in batch:
                self._file_versions[sha1] = found.get(sha1)
        return {sha1: self._file_versions[sha1] for sha1 in sha1_list if self._file_versions.get(sha1)}

    def installed_versions(self, sha1_list: list[str]) -> dict[str, dict]:
        """Hash SHA-1 -> versión completa de Modrinth (incluye game_versions y loaders). Usa la caché de sesión."""
        return self._versions_by_hash(sha1_list)

    def installed_projects(self, sha1_list: list[str]) -> dict[str, str]:
        """Hash SHA-1 -> ID de proyecto. Los archivos no reconocidos no aparecen. Usa la caché de sesión."""
        return {sha1: version["project_id"] for sha1, version in self._versions_by_hash(sha1_list).items()}

    def sides(self, project_ids: list[str]) -> dict[str, dict]:
        """ID de proyecto -> {title, client, server}. Valores de Modrinth: required, optional, unsupported, unknown."""
        result: dict[str, dict] = {}
        unique = list(dict.fromkeys(project_ids))
        for start in range(0, len(unique), BATCH):
            batch = unique[start:start + BATCH]
            data = http_client.get_json(f"{BASE_URL}/projects", self._cache, params={"ids": json.dumps(batch)})
            for project in data:
                result[project["id"]] = {
                    "title": project.get("title", project["id"]),
                    "client": project.get("client_side", "unknown"),
                    "server": project.get("server_side", "unknown"),
                }
        return result

    def plan_project(self, project_id: str, minecraft_version: str, loader: str, installed: set[str]) -> list[dict]:
        """Versión principal y sus dependencias obligatorias, sin descargar nada."""
        candidates = self.project_versions(project_id, minecraft_version, loader)
        if not candidates:
            raise ModrinthError(f"No hay versión de {project_id} para {minecraft_version} ({loader}).")
        return self._resolve_plan(candidates[0], minecraft_version, loader, set(installed))

    def project_by_slug(self, slug: str) -> dict | None:
        """Proyecto por slug o ID; None si Modrinth no lo conoce (404)."""
        response = http_client.client().get(f"{BASE_URL}/project/{slug}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def _find_project(self, dep_id: str, minecraft_version: str, loader: str) -> dict | None:
        """Proyecto de Modrinth para un ID de mod: prueba slugs probables y, si no existe, busca por nombre exacto."""
        base = dep_id.lower()
        if base.startswith("fabric-"):
            slugs = ["fabric-api"]  # módulos internos que vienen con Fabric API
        else:
            slugs = list(dict.fromkeys([base, base.replace("_", "-")]))
        for slug in slugs:
            project = self.project_by_slug(slug)
            if project is not None and str(project.get("slug", "")).lower() == slug:
                return project
        wanted = base.replace("_", "-")
        for hit in self.search(dep_id, minecraft_version, loader, limit=10):
            if str(hit.get("slug", "")).lower() == wanted:
                return {"id": hit["project_id"], "slug": hit["slug"], "title": hit.get("title", dep_id)}
        return None

    def plan_for_dependencies(self, dep_ids: list[str], minecraft_version: str, loader: str,
                              installed: set[str]) -> tuple[list[dict], list[str]]:
        """Plan para dependencias faltantes dadas por ID de mod. Devuelve (plan, motivos de lo no encontrado)."""
        plan: list[dict] = []
        not_found: list[str] = []
        taken = set(installed)
        for dep_id in dep_ids:
            project = self._find_project(dep_id, minecraft_version, loader)
            if project is None:
                not_found.append(f"{dep_id}: no hay un proyecto con ese nombre en Modrinth")
                continue
            if project["id"] in taken:
                continue
            candidates = self.project_versions(project["id"], minecraft_version, loader)
            if not candidates:
                not_found.append(f"{dep_id}: «{project.get('title', dep_id)}» no tiene versión para "
                                 f"Minecraft {minecraft_version} ({loader})")
                continue
            try:
                resolved = self._resolve_plan(candidates[0], minecraft_version, loader, taken)
            except ModrinthError as error:
                not_found.append(f"{dep_id}: {error}")
                continue
            for version in resolved:
                taken.add(version["project_id"])
                plan.append(version)
        return plan, not_found

    def install_project(self, project_id: str, minecraft_version: str, loader: str,
                        mods_dir: Path, installed_projects: frozenset[str] = frozenset()) -> list[Path]:
        plan = self.plan_project(project_id, minecraft_version, loader, set(installed_projects))
        return self.download_plan(plan, mods_dir)

    def _resolve_plan(self, first: dict, minecraft_version: str, loader: str, installed: set[str]) -> list[dict]:
        """Dependencias obligatorias en anchura (BFS): cada proyecto se consulta una sola vez."""
        plan, queue = [first], deque([first])
        visited = {first["project_id"]} | installed
        while queue:
            current = queue.popleft()
            for dep in current.get("dependencies", []):
                if dep.get("dependency_type") != "required":
                    continue
                project_id = dep.get("project_id") or self._project_of_version(dep.get("version_id"))
                if not project_id or project_id in visited:
                    continue
                visited.add(project_id)
                candidates = self.project_versions(project_id, minecraft_version, loader)
                if not candidates:
                    raise ModrinthError(f"Falta «{self._title(project_id)}» para Minecraft "
                                        f"{minecraft_version} ({loader}).")
                plan.append(candidates[0])
                queue.append(candidates[0])
        return plan

    def _project_of_version(self, version_id: str | None) -> str | None:
        """Algunas dependencias solo traen el ID de versión; de ahí se obtiene el proyecto."""
        if not version_id:
            return None
        version = http_client.get_json(f"{BASE_URL}/version/{version_id}", self._cache)
        return version.get("project_id")

    def _title(self, project_id: str) -> str:
        try:
            project = self.project_by_slug(project_id)
        except Exception:  # solo para el mensaje de error: si falla, se muestra el ID
            project = None
        return project.get("title", project_id) if project else project_id

    def download_plan(self, plan: list[dict], mods_dir: Path) -> list[Path]:
        jobs = []
        for version in plan:
            files = version.get("files") or []
            if not files:
                raise ModrinthError(f"La versión {version.get('version_number', '?')} no tiene archivos.")
            file = next((f for f in files if f.get("primary")), files[0])
            target = validators.ensure_inside(mods_dir, mods_dir / file["filename"])
            jobs.append((file["url"], target, file.get("hashes", {}).get("sha1")))
        mods_dir.mkdir(parents=True, exist_ok=True)
        return http_client.download_many(jobs)