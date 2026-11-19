"""Cliente HTTP compartido: conexión reutilizable, reintentos, caché ETag y descargas paralelas."""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx

from utils import file_manager

USER_AGENT = "MinecraftServerManager/0.2 (reemplazar por tu contacto)"
_CHUNK = 64 * 1024
_client: httpx.Client | None = None

Job = tuple[str, Path, str | None]  # (url, destino, sha1 esperado o None)


class DownloadError(RuntimeError):
    """Descarga fallida o archivo que no supera la verificación de hash."""


def client() -> httpx.Client:
    """Un solo cliente para toda la aplicación: reutiliza conexiones TLS en vez de abrir una por petición."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(
            timeout=httpx.Timeout(20.0, connect=10.0),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            transport=httpx.HTTPTransport(retries=2),
        )
    return _client


def close() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def get_json(url: str, cache_dir: Path | None = None, params: dict | None = None) -> Any:
    """GET JSON. Con cache_dir envía If-None-Match: un 304 evita volver a bajar el cuerpo."""
    if cache_dir is None:
        response = client().get(url, params=params)
        response.raise_for_status()
        return response.json()
    key = hashlib.sha256(f"{url}|{sorted((params or {}).items())}".encode()).hexdigest()[:24]
    body_file, etag_file = cache_dir / f"{key}.json", cache_dir / f"{key}.etag"
    headers = {}
    if body_file.is_file() and etag_file.is_file():
        headers["If-None-Match"] = etag_file.read_text(encoding="ascii").strip()
    response = client().get(url, params=params, headers=headers)
    if response.status_code == 304:
        return json.loads(body_file.read_bytes())
    response.raise_for_status()
    cache_dir.mkdir(parents=True, exist_ok=True)
    body_file.write_bytes(response.content)
    etag = response.headers.get("etag")
    if etag:
        etag_file.write_text(etag, encoding="ascii")
    else:
        etag_file.unlink(missing_ok=True)
    return response.json()


def get_text_or_none(url: str) -> str | None:
    """Texto del recurso, o None si el proveedor no lo publica (404)."""
    response = client().get(url)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.text.strip()


def download_file(url: str, target: Path, expected_sha1: str | None = None, progress=None) -> Path:
    """Descarga por streaming a un .part, verifica SHA-1 y solo entonces reemplaza el destino."""
    if not url.startswith("https://"):
        raise DownloadError("Solo se permiten descargas HTTPS.")
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    digest = hashlib.sha1()
    try:
        with client().stream("GET", url) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            done = 0
            with partial.open("wb") as file:
                for chunk in response.iter_bytes(_CHUNK):
                    file.write(chunk)
                    digest.update(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
        if expected_sha1 and digest.hexdigest() != expected_sha1.lower():
            raise DownloadError("El SHA-1 no coincide; la descarga se descartó.")
        os.replace(partial, target)
        return target
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def download_many(jobs: Iterable[Job], max_workers: int = 4) -> list[Path]:
    """Descarga en paralelo. Si el archivo ya existe con el SHA-1 correcto, no se vuelve a bajar."""
    jobs = list(jobs)
    client()  # se crea antes de lanzar hilos para evitar carreras al inicializarlo

    def run(job: Job) -> Path:
        url, target, sha1 = job
        if sha1 and target.is_file() and file_manager.sha1_of(target) == sha1.lower():
            return target
        return download_file(url, target, expected_sha1=sha1)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(run, jobs))
