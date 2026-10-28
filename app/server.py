import asyncio
import json
import logging
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.canvas_api import canvas_client
from app.config import (
    BASE_DIR,
    CANVAS_BASE_URL,
    get_download_path,
    get_settings,
    save_settings,
)
from app.downloader import bulk_downloader, open_in_file_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

app = FastAPI(title="CanvasDL Mission Control", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def no_stale_frontend(request: Request, call_next):
    # Sin esto el navegador sigue usando app.js viejo tras actualizar el código
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache"
    return response


STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


class DownloadRequest(BaseModel):
    items: List[Dict[str, Any]]


class SettingsUpdate(BaseModel):
    download_dir: Optional[str] = None
    max_concurrent_downloads: Optional[int] = None
    auto_open_folder: Optional[bool] = None


class TokenUpdate(BaseModel):
    token: str


@app.get("/api/status")
def get_system_status():
    auth_info = canvas_client.verify_auth()
    download_path = get_download_path()

    # Espacio libre en disco
    free_gb = 0
    total_gb = 0
    try:
        usage = shutil.disk_usage(download_path)
        free_gb = round(usage.free / (1024**3), 1)
        total_gb = round(usage.total / (1024**3), 1)
    except Exception:
        pass

    settings = get_settings()
    dl_status = bulk_downloader.get_status()

    return {
        "canvas_url": CANVAS_BASE_URL,
        "authenticated": auth_info["authenticated"],
        "user": auth_info["user"],
        "auth_error": auth_info["error"],
        "download_dir": str(download_path),
        "disk_free_gb": free_gb,
        "disk_total_gb": total_gb,
        "settings": settings,
        "downloads": dl_status,
    }


@app.get("/api/courses")
def list_courses():
    try:
        courses = canvas_client.get_courses()
        return {"courses": courses, "total": len(courses)}
    except Exception as e:
        logger.error(f"Error cargando cursos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/courses/{course_id}/modules")
def get_course_modules(course_id: int):
    try:
        modules = canvas_client.get_course_modules(course_id)
        return {"course_id": course_id, "modules": modules}
    except Exception as e:
        logger.error(f"Error cargando módulos de curso {course_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/courses/{course_id}/files")
def get_course_files(course_id: int):
    try:
        data = canvas_client.get_course_folders_and_files(course_id)
        return {"course_id": course_id, **data}
    except Exception as e:
        logger.error(f"Error cargando archivos de curso {course_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/courses/{course_id}/assignments")
def get_course_assignments(course_id: int):
    try:
        assignments = canvas_client.get_course_assignments(course_id)
        return {"course_id": course_id, "assignments": assignments, "total": len(assignments)}
    except Exception as e:
        logger.error(f"Error cargando tareas de curso {course_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/courses/{course_id}/full-plan")
def get_full_course_plan(course_id: int, course_name: str):
    try:
        return canvas_client.get_full_course_plan(course_id, course_name)
    except Exception as e:
        logger.error(f"Error armando descarga completa de curso {course_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/downloads/start")
async def start_downloads(req: DownloadRequest):
    if not req.items:
        raise HTTPException(status_code=400, detail="No se enviaron archivos para descargar")

    token = canvas_client.get_token()
    result = await bulk_downloader.add_and_start(req.items, token=token)
    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])
    return result


@app.post("/api/downloads/cancel")
def cancel_downloads():
    bulk_downloader.cancel_all()
    return {"success": True, "message": "Descargas canceladas"}


@app.get("/api/downloads/status")
def get_download_status():
    return bulk_downloader.get_status()


@app.get("/api/downloads/events")
async def download_events(request: Request):
    """Canal SSE para actualizaciones en vivo de descargas."""
    async def event_generator():
        q = bulk_downloader.subscribe()
        try:
            # Emitir estado inicial
            initial_data = json.dumps({
                "type": "init",
                "data": bulk_downloader.get_status(),
            })
            yield f"data: {initial_data}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    # Esperar siguiente evento con timeout para enviar ping heartbeat
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Enviar ping para mantener la conexión viva
                    yield f": ping\n\n"
        finally:
            bulk_downloader.unsubscribe(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/settings")
def read_settings():
    return get_settings()


@app.post("/api/settings")
def update_settings(update: SettingsUpdate):
    data = update.dict(exclude_unset=True)
    new_settings = save_settings(data)
    return {"success": True, "settings": new_settings}


@app.post("/api/open-folder")
def open_folder():
    path = get_download_path()
    ok = open_in_file_manager(path)
    return {"success": ok, "path": str(path)}


@app.post("/api/auth/token")
def update_token(body: TokenUpdate):
    if not body.token.strip():
        raise HTTPException(status_code=400, detail="Token vacío")
    canvas_client.set_token(body.token.strip())
    verify = canvas_client.verify_auth()
    return verify


@app.get("/")
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        # ?v=mtime fuerza al navegador a bajar el JS/CSS nuevo cuando cambian
        html = index_file.read_text(encoding="utf-8")
        for name in ("app.js", "style.css"):
            v = int((STATIC_DIR / name).stat().st_mtime)
            html = html.replace(f"/static/{name}", f"/static/{name}?v={v}")
        return HTMLResponse(html)
    return {"message": "CanvasDL API activa. Frontend no encontrado en static/index.html"}


# Montar archivos estáticos
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
