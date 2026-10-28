import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import logging
import os
from pathlib import Path
import platform
import re
import subprocess
import time
from typing import Any, AsyncGenerator, Dict, List, Optional
import urllib.parse
import requests

from app.config import CANVAS_BASE_URL, get_download_path, get_settings

logger = logging.getLogger("downloader")


def sanitize_filename(name: str) -> str:
    """Elimina o reemplaza caracteres no válidos para sistemas de archivos y previene path traversal (ISO 27001 8.28)."""
    if not name:
        return "archivo"
    # Reemplazar caracteres no permitidos en Linux/Windows y caracteres de control
    cleaned = re.sub(r'[\x00-\x1f\\/*?:"<>|]', "_", name).strip()
    # Eliminar secuencias '..' para evitar path traversal
    while ".." in cleaned:
        cleaned = cleaned.replace("..", "_")
    # Eliminar puntos y espacios al inicio y final
    cleaned = re.sub(r"^\.+|\.+$", "", cleaned).strip()
    # Nombres reservados en Windows
    reserved = {"con", "prn", "aux", "nul", "com1", "com2", "com3", "com4", "com5",
                "com6", "com7", "com8", "com9", "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9"}
    if cleaned.lower() in reserved:
        cleaned = f"_{cleaned}"
    return cleaned or "archivo"


class DownloadTask:
    def __init__(
        self,
        task_id: str,
        course_name: str,
        folder_or_module: str,
        filename: str,
        url: str,
        size: int = 0,
        file_id: Optional[int] = None,
        raw_content: Optional[str] = None,
    ):
        self.task_id = task_id
        self.course_name = sanitize_filename(course_name)
        # "Tareas/Tarea 1" -> subcarpetas; cada segmento se sanea por separado (sin "..")
        parts = [sanitize_filename(p) for p in (folder_or_module or "").split("/") if p.strip()]
        self.folder_or_module = "/".join(parts) or "General"
        self.filename = sanitize_filename(filename)
        self.url = url
        self.size = size
        self.file_id = file_id
        self.raw_content = raw_content

        self.status = "queued"  # queued, downloading, completed, skipped, failed, cancelled
        self.downloaded_bytes = 0
        self.error_message: Optional[str] = None
        self.destination_path: Optional[str] = None
        self.speed: float = 0.0  # bytes por segundo
        self.sha256: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "course_name": self.course_name,
            "folder_or_module": self.folder_or_module,
            "filename": self.filename,
            "size": self.size,
            "status": self.status,
            "downloaded_bytes": self.downloaded_bytes,
            "speed": self.speed,
            "error_message": self.error_message,
            "destination_path": self.destination_path,
        }


class BulkDownloader:
    def __init__(self):
        self.tasks: Dict[str, DownloadTask] = {}
        self.is_running: bool = False
        self.is_cancelled: bool = False
        self.subscribers: List[asyncio.Queue] = []
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._lock = asyncio.Lock()
        self.session = requests.Session()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self.subscribers:
            self.subscribers.remove(q)

    async def broadcast(self, event_type: str, data: Dict[str, Any]) -> None:
        message = {"type": event_type, "data": data, "timestamp": time.time()}
        for q in list(self.subscribers):
            try:
                q.put_nowait(message)
            except Exception:
                pass

    def get_status(self) -> Dict[str, Any]:
        total_tasks = len(self.tasks)
        completed = sum(1 for t in self.tasks.values() if t.status == "completed")
        skipped = sum(1 for t in self.tasks.values() if t.status == "skipped")
        failed = sum(1 for t in self.tasks.values() if t.status == "failed")
        downloading = sum(1 for t in self.tasks.values() if t.status == "downloading")
        queued = sum(1 for t in self.tasks.values() if t.status == "queued")

        total_bytes = sum(t.size for t in self.tasks.values())
        downloaded_bytes = sum(t.downloaded_bytes for t in self.tasks.values())

        return {
            "is_running": self.is_running,
            "total_tasks": total_tasks,
            "completed": completed,
            "skipped": skipped,
            "failed": failed,
            "downloading": downloading,
            "queued": queued,
            "total_bytes": total_bytes,
            "downloaded_bytes": downloaded_bytes,
            "tasks": [t.to_dict() for t in self.tasks.values()],
        }

    def cancel_all(self) -> None:
        self.is_cancelled = True
        self.is_running = False
        for t in self.tasks.values():
            if t.status in ("queued", "downloading"):
                t.status = "cancelled"

    async def add_and_start(self, items: List[Dict[str, Any]], token: Optional[str] = None,
                            download_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Añade una lista de items e inicia la descarga concurrente en segundo plano."""
        if self.is_running:
            return {"error": "Ya hay una descarga en curso"}

        self.tasks.clear()
        self.is_cancelled = False
        self.is_running = True
        claimed: set = set()

        for idx, item in enumerate(items):
            task_id = f"task_{idx}_{int(time.time()*1000)}"
            task = DownloadTask(
                task_id=task_id,
                course_name=item.get("course_name", "Curso"),
                folder_or_module=item.get("module_name") or item.get("folder_name", "General"),
                filename=item.get("filename", f"archivo_{idx}"),
                url=item.get("url") or item.get("download_url", ""),
                size=item.get("size", 0),
                file_id=item.get("file_id"),
                raw_content=item.get("raw_content"),
            )
            # Dos items distintos con el mismo nombre en la misma carpeta no se pisan
            stem, ext = os.path.splitext(task.filename)
            n = 2
            while (key := (task.course_name, task.folder_or_module, task.filename.lower())) in claimed:
                task.filename = f"{stem} ({n}){ext}"
                n += 1
            claimed.add(key)
            self.tasks[task_id] = task

        # Lanzar tarea de fondo asíncrona
        asyncio.create_task(self._process_queue(token, download_dir))
        await self.broadcast("batch_started", self.get_status())
        return {"success": True, "total_queued": len(self.tasks)}

    async def _process_queue(self, token: Optional[str], download_dir: Optional[Path]) -> None:
        loop = asyncio.get_running_loop()
        base_download_dir = (download_dir or get_download_path()).expanduser().resolve()
        settings = get_settings()
        max_workers = settings.get("max_concurrent_downloads", 4)

        semaphore = asyncio.Semaphore(max_workers)

        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            headers["User-Agent"] = "CanvasDL/1.0"

        async def worker(task: DownloadTask):
            async with semaphore:
                if self.is_cancelled:
                    task.status = "cancelled"
                    return

                await loop.run_in_executor(
                    self._executor,
                    self._download_single_file,
                    task,
                    base_download_dir,
                    headers,
                )
                await self.broadcast("task_updated", task.to_dict())

        tasks_coroutines = [worker(t) for t in self.tasks.values()]
        await asyncio.gather(*tasks_coroutines, return_exceptions=True)

        if not self.is_cancelled:
            for task in self._remove_duplicates():
                await self.broadcast("task_updated", task.to_dict())

        self.is_running = False
        final_status = self.get_status()
        await self.broadcast("batch_finished", final_status)

        # Abrir carpeta automáticamente si está configurado
        if settings.get("auto_open_folder"):
            open_in_file_manager(base_download_dir)

    def _remove_duplicates(self) -> List[DownloadTask]:
        """
        Borra copias con contenido idéntico (mismo SHA-256) y conserva la primera
        según el orden del lote (módulos > tareas > anuncios > archivos).
        """
        # ponytail: los duplicados se re-descargan en cada corrida antes de borrarse; cachear hashes si molesta
        kept: Dict[str, DownloadTask] = {}
        removed: List[DownloadTask] = []
        for task in self.tasks.values():
            if task.status not in ("completed", "skipped") or not task.sha256:
                continue
            first = kept.setdefault(task.sha256, task)
            if first is task or first.destination_path == task.destination_path:
                continue
            try:
                Path(task.destination_path).unlink(missing_ok=True)
            except OSError as e:
                logger.warning(f"No se pudo borrar duplicado {task.destination_path}: {e}")
                continue
            task.status = "skipped"
            task.error_message = f"Duplicado de {first.destination_path}"
            task.destination_path = first.destination_path
            removed.append(task)
        if removed:
            logger.info(f"{len(removed)} archivos duplicados eliminados")
        return removed

    def _download_single_file(
        self,
        task: DownloadTask,
        base_dir: Path,
        headers: Dict[str, str],
    ) -> None:
        if self.is_cancelled:
            task.status = "cancelled"
            return

        # Construir ruta de destino: [base_dir] / [Curso] / [Módulo] / [Archivo]
        base_dir_resolved = base_dir.resolve()
        course_dir = (base_dir_resolved / task.course_name).resolve()
        target_dir = (course_dir / task.folder_or_module).resolve()

        # ISO 27001 8.28 / SOC 2 CC6.8: Boundary assertion
        if not target_dir.is_relative_to(base_dir_resolved):
            task.status = "failed"
            task.error_message = "Directorio de destino no válido (violación de límites de seguridad)"
            logger.error(f"Intento de path traversal bloqueado: {target_dir} fuera de {base_dir_resolved}")
            return

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Error creando directorio {target_dir}: {e}")
            target_dir = course_dir
            target_dir.mkdir(parents=True, exist_ok=True)

        target_file = (target_dir / task.filename).resolve()
        if not target_file.is_relative_to(base_dir_resolved):
            task.status = "failed"
            task.error_message = "Nombre de archivo no válido (violación de límites de seguridad)"
            logger.error(f"Intento de path traversal en archivo bloqueado: {target_file}")
            return

        task.destination_path = str(target_file)

        # Si es contenido en texto/HTML directo (ej: enunciado de tarea)
        if task.raw_content is not None:
            task.status = "downloading"
            try:
                data = task.raw_content.encode("utf-8")
                target_file.write_bytes(data)
                task.sha256 = hashlib.sha256(data).hexdigest()
                task.status = "completed"
                task.downloaded_bytes = len(data)
                return
            except Exception as e:
                task.status = "failed"
                task.error_message = str(e)
                return

        # Si el archivo ya existe y tiene el tamaño esperado, lo saltamos
        if target_file.exists():
            existing_size = target_file.stat().st_size
            if task.size > 0 and existing_size == task.size:
                with open(target_file, "rb") as f:
                    task.sha256 = hashlib.file_digest(f, "sha256").hexdigest()
                task.status = "skipped"
                task.downloaded_bytes = existing_size
                return

        task.status = "downloading"
        temp_file = target_dir / f"{task.filename}.crdownload"

        try:
            stream_url = task.url
            if not stream_url.startswith("http"):
                task.status = "failed"
                task.error_message = "URL inválida"
                return

            # Si la URL es de la API Canvas (ej: /api/v1/files/...), obtener la URL de descarga directa
            if "/api/v1/files/" in stream_url:
                try:
                    meta_resp = self.session.get(stream_url, headers=headers, timeout=15)
                    if meta_resp.status_code == 200:
                        m_data = meta_resp.json()
                        if isinstance(m_data, dict) and m_data.get("url"):
                            stream_url = m_data["url"]
                except Exception as e:
                    logger.warning(f"No se pudo resolver URL API {stream_url}: {e}")

            # ISO 27001 8.20 / SOC 2 CC6.6: Only send Authorization Bearer header to the Canvas domain.
            # External presigned URLs (e.g. AWS S3, CloudFront) must NOT receive Canvas LMS credentials.
            download_headers = {"User-Agent": "CanvasDL/1.0"}
            stream_netloc = urllib.parse.urlparse(stream_url).netloc.lower()
            canvas_netloc = urllib.parse.urlparse(CANVAS_BASE_URL).netloc.lower()
            if stream_netloc == canvas_netloc and "Authorization" in headers:
                download_headers["Authorization"] = headers["Authorization"]

            with self.session.get(stream_url, headers=download_headers, stream=True, timeout=30) as resp:
                if resp.status_code not in (200, 302, 304):
                    task.status = "failed"
                    task.error_message = f"HTTP {resp.status_code}"
                    return

                total_content_length = int(resp.headers.get("Content-Length", task.size or 0))
                if total_content_length > 0:
                    task.size = total_content_length

                bytes_written = 0
                start_time = time.time()
                last_speed_check = start_time
                last_bytes_check = 0
                hasher = hashlib.sha256()

                with open(temp_file, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if self.is_cancelled:
                            task.status = "cancelled"
                            break
                        if chunk:
                            f.write(chunk)
                            hasher.update(chunk)
                            bytes_written += len(chunk)
                            task.downloaded_bytes = bytes_written

                            now = time.time()
                            if now - last_speed_check >= 0.5:
                                delta_time = now - last_speed_check
                                delta_bytes = bytes_written - last_bytes_check
                                task.speed = delta_bytes / delta_time if delta_time > 0 else 0
                                last_speed_check = now
                                last_bytes_check = bytes_written

                if self.is_cancelled:
                    if temp_file.exists():
                        temp_file.unlink(missing_ok=True)
                    task.status = "cancelled"
                    return

                # Renombrar archivo temporal a definitivo
                if temp_file.exists():
                    temp_file.replace(target_file)
                task.sha256 = hasher.hexdigest()
                task.status = "completed"
                task.downloaded_bytes = bytes_written

        except Exception as e:
            logger.error(f"Error descargando {task.filename}: {e}")
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)
            task.status = "failed"
            task.error_message = str(e)


def open_in_file_manager(folder_path: Path) -> bool:
    """Abre la carpeta en el explorador de archivos del sistema operativo."""
    try:
        current_os = platform.system()
        path_str = str(folder_path.resolve())

        if current_os == "Linux":
            subprocess.Popen(["xdg-open", path_str])
            return True
        elif current_os == "Darwin":
            subprocess.Popen(["open", path_str])
            return True
        elif current_os == "Windows":
            os.startfile(path_str)
            return True
    except Exception as e:
        logger.warning(f"No se pudo abrir explorador para {folder_path}: {e}")
    return False


bulk_downloader = BulkDownloader()
