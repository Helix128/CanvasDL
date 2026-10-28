"""Shared operations for local CLI and MCP clients."""

import asyncio
import shutil
from pathlib import Path
from typing import Any

from app.canvas_api import canvas_client
from app.config import get_download_path, get_settings
from app.downloader import bulk_downloader


def course_name(course_id: int) -> str:
    for course in canvas_client.get_courses():
        if int(course["id"]) == course_id:
            return course["name"]
    raise ValueError(f"Curso {course_id} no encontrado o no accesible")


async def start_download_items(items: list[dict[str, Any]], download_dir: str | None = None) -> dict[str, Any]:
    if not items:
        raise ValueError("No hay archivos para descargar")
    destination = Path(download_dir).expanduser().resolve() if download_dir else None
    result = await bulk_downloader.add_and_start(items, token=canvas_client.get_token(), download_dir=destination)
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


async def download_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    await start_download_items(items)
    while bulk_downloader.is_running:
        await asyncio.sleep(0.25)
    return bulk_downloader.get_status()


async def download_course(course_id: int) -> dict[str, Any]:
    name = course_name(course_id)
    plan = canvas_client.get_full_course_plan(course_id, name)
    status = await download_items(plan["items"])
    return {"course_id": course_id, "download_dir": str(get_download_path()), "status": status,
            "plan_errors": plan["errors"]}


async def start_course_download(course_id: int, download_dir: str | None = None) -> dict[str, Any]:
    name = course_name(course_id)
    plan = canvas_client.get_full_course_plan(course_id, name)
    destination = Path(download_dir).expanduser().resolve() if download_dir else get_download_path()
    result = await start_download_items(plan["items"], str(destination))
    return {**result, "course_id": course_id, "download_dir": str(destination),
            "plan_errors": plan["errors"]}


def list_cached_files() -> list[dict[str, str]]:
    root = get_download_path().resolve()
    return [{"path": str(path.relative_to(root)), "size": path.stat().st_size}
            for path in root.rglob("*") if path.is_file() and not path.is_symlink()]


def copy_cached_files(paths: list[str], destination_dir: str) -> dict[str, Any]:
    root = get_download_path().resolve()
    destination = Path(destination_dir).expanduser().resolve()
    copied = []
    for relative in paths:
        source = (root / relative).resolve()
        if not source.is_relative_to(root) or not source.is_file():
            raise ValueError(f"Archivo de caché inválido: {relative}")
        target = (destination / source.relative_to(root)).resolve()
        if not target.is_relative_to(destination):
            raise ValueError(f"Ruta de destino inválida (fuera del límite permitido): {target}")
        if target.exists():
            raise FileExistsError(f"El archivo ya existe: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(str(target))
    return {"copied": copied, "destination_dir": str(destination)}


def download_status() -> dict[str, Any]:
    return {"download_dir": str(get_download_path()), "settings": get_settings(),
            "downloads": bulk_downloader.get_status()}
