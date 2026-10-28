from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html import escape
import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
import urllib.parse
import requests

from app.config import (
    CANVAS_BASE_URL,
    TOKEN_FILE,
    get_token as config_get_token,
    save_token as config_save_token,
)

logger = logging.getLogger("canvas_api")


def _seg(name: str) -> str:
    """Nombre seguro para usar como un solo segmento de carpeta (sin '/')."""
    return (name or "").replace("/", "-").replace("\\", "-").strip() or "Sin nombre"


def _fmt_date(iso: Optional[str]) -> Optional[str]:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso


def _html_doc(title: str, meta: List[Tuple[str, Any]], body: str) -> str:
    """Envuelve HTML de Canvas (enunciado, anuncio, página) en un documento autónomo."""
    rows = "<br>".join(f"<strong>{escape(k)}:</strong> {escape(str(v))}" for k, v in meta if v not in (None, ""))
    return (
        '<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">'
        f"<title>{escape(title)}</title>"
        "<style>body{font-family:sans-serif;padding:2.5rem;max-width:850px;margin:auto;line-height:1.6;color:#1e293b;}"
        "h1{color:#2563eb;}hr{border:0;border-top:1px solid #cbd5e1;margin:1.5rem 0;}"
        "table{border-collapse:collapse;}td,th{border:1px solid #cbd5e1;padding:.3rem .6rem;}img{max-width:100%;}</style>"
        f"</head><body><h1>{escape(title)}</h1><p>{rows}</p><hr>{body}</body></html>"
    )


def _rubric_html(rubric: Optional[List[Dict[str, Any]]], title: str = "") -> str:
    """Tabla HTML de la rúbrica de Canvas: criterios, puntaje y niveles de logro."""
    if not rubric:
        return ""
    rows = []
    for c in rubric:
        ratings = "".join(
            f"<li><strong>{escape(str(r.get('points', '')))} pts</strong> · {escape(r.get('description') or '')}"
            + (f"<br><small>{escape(r['long_description'])}</small>" if r.get("long_description") else "")
            + "</li>"
            for r in c.get("ratings") or []
        )
        long_desc = f"<br><small>{escape(c['long_description'])}</small>" if c.get("long_description") else ""
        rows.append(
            f"<tr><td><strong>{escape(c.get('description') or '')}</strong>{long_desc}</td>"
            f"<td>{escape(str(c.get('points', '')))}</td><td><ul>{ratings}</ul></td></tr>"
        )
    total = sum(c.get("points") or 0 for c in rubric)
    return (
        f"<hr><h2>Rúbrica{(': ' + escape(title)) if title else ''}</h2>"
        "<table><tr><th>Criterio</th><th>Puntos</th><th>Niveles de logro</th></tr>"
        + "".join(rows) + f"</table><p><strong>Total:</strong> {total} pts</p>"
    )


def _file_entry(f: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza un objeto File crudo de Canvas al formato de item de archivo."""
    return {
        "file_id": f.get("id"),
        "filename": f.get("display_name") or f.get("filename") or f"archivo_{f.get('id')}",
        "size": f.get("size", 0),
        "download_url": f.get("url"),
    }


class CanvasClient:
    def __init__(self, base_url: str = CANVAS_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self._file_cache: Dict[int, Dict[str, Any]] = {}

    def get_token(self) -> Optional[str]:
        return config_get_token()

    def set_token(self, token: str) -> None:
        config_save_token(token)

    def get_headers(self) -> Dict[str, str]:
        token = self.get_token()
        if not token:
            return {}
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "CanvasDL/1.0",
        }

    def verify_auth(self) -> Dict[str, Any]:
        """Verifica si el token actual es válido y retorna datos del usuario."""
        token = self.get_token()
        if not token:
            return {"authenticated": False, "user": None, "error": "No hay token configurado"}

        try:
            resp = self.session.get(
                f"{self.base_url}/api/v1/users/self",
                headers=self.get_headers(),
                timeout=10,
            )
            if resp.status_code == 200:
                user_data = resp.json()
                return {"authenticated": True, "user": user_data, "error": None}
            else:
                return {
                    "authenticated": False,
                    "user": None,
                    "error": f"Token inválido o expirado (HTTP {resp.status_code})",
                }
        except Exception as e:
            return {"authenticated": False, "user": None, "error": f"Error de red: {str(e)}"}

    def _paginate(self, url: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Recorre la paginación estándar de Canvas usando cabeceras Link."""
        items: List[Dict[str, Any]] = []
        current_url: Optional[str] = url
        current_params = dict(params or {})
        current_params.setdefault("per_page", 100)

        while current_url:
            resp = self.session.get(
                current_url,
                headers=self.get_headers(),
                params=current_params,
                timeout=15,
            )
            if resp.status_code != 200:
                logger.error(f"Error {resp.status_code} al consultar {current_url}: {resp.text}")
                break

            data = resp.json()
            if isinstance(data, list):
                items.extend(data)
            else:
                # En caso de endpoint no-lista
                items.append(data)
                break

            # Siguiente página
            if "next" in resp.links:
                next_url = resp.links["next"]["url"]
                parsed_base = urllib.parse.urlparse(self.base_url)
                parsed_next = urllib.parse.urlparse(next_url)
                if parsed_next.netloc == parsed_base.netloc and parsed_next.scheme in ("https", "http"):
                    current_url = next_url
                    current_params = {}  # Los parámetros ya vienen en la URL next
                else:
                    logger.warning(f"Enlace de paginación externo rechazado por seguridad (ISO 27001 8.20): {next_url}")
                    current_url = None
            else:
                current_url = None

        return items

    def api_get(self, path: str, params: Optional[Dict[str, Any]] = None, max_items: int = 500) -> Any:
        """GET de solo lectura a cualquier endpoint /api/v1 de esta instancia, siguiendo paginación."""
        if not path.startswith("/api/v1/") or ".." in path or "://" in path or "\\" in path:
            raise ValueError("path debe ser relativo y empezar con /api/v1/ (ej. /api/v1/users/self)")
        url: Optional[str] = self.base_url + path
        current_params = {"per_page": 100, **(params or {})}
        items: List[Any] = []
        while url:
            # El token viaja en cada request: nunca seguir enlaces fuera de esta instancia Canvas
            parsed_base = urllib.parse.urlparse(self.base_url)
            parsed_target = urllib.parse.urlparse(url)
            if parsed_target.netloc != parsed_base.netloc or parsed_target.scheme not in ("https", "http"):
                logger.warning(f"URL rechazada por estar fuera del dominio de Canvas: {url}")
                break
            resp = self.session.get(url, headers=self.get_headers(), params=current_params, timeout=30)
            if resp.status_code != 200:
                raise RuntimeError(f"Canvas HTTP {resp.status_code} en {path}: {resp.text[:500]}")
            data = resp.json()
            if not isinstance(data, list):
                return data
            items.extend(data)
            if len(items) >= max_items:
                return {"items": items[:max_items], "truncated": True}
            url = resp.links.get("next", {}).get("url")
            current_params = {}
        return items

    def get_favorite_course_ids(self) -> set[int]:
        """Obtiene el conjunto de IDs de cursos marcados como favoritos en el Dashboard."""
        try:
            resp = self.session.get(
                f"{self.base_url}/api/v1/users/self/favorites/courses",
                headers=self.get_headers(),
                timeout=10,
            )
            if resp.status_code == 200:
                favs = resp.json()
                return {f["id"] for f in favs if isinstance(f, dict) and "id" in f}
        except Exception as e:
            logger.warning(f"No se pudieron cargar favoritos: {e}")
        return set()

    def get_courses(self) -> List[Dict[str, Any]]:
        """Obtiene la lista completa de cursos separando activos de concluidos."""
        fav_ids = self.get_favorite_course_ids()

        raw_courses = self._paginate(
            f"{self.base_url}/api/v1/courses",
            params={
                "include[]": ["term", "teachers", "course_image", "total_students"],
            },
        )

        processed = []
        for c in raw_courses:
            if not isinstance(c, dict) or "id" not in c or not c.get("name"):
                continue

            cid = c["id"]
            term_info = c.get("term") or {}
            term_name = term_info.get("name") or "Sin período"

            is_fav = cid in fav_ids
            workflow_state = c.get("workflow_state", "")
            concluded = bool(c.get("concluded"))

            # Detección inteligente de curso activo
            # Un curso es activo si:
            # 1. Es favorito en el dashboard, o
            # 2. workflow_state es 'available' y no está concluido y su término es actual (ACTIVOS o 2026)
            is_term_active = bool(
                re.search(r"ACTIVOS|2026", term_name, re.IGNORECASE)
                or (not concluded and workflow_state == "available" and not re.search(r"202[0-5]", term_name))
            )
            is_active = is_fav or (is_term_active and not concluded)

            teachers = []
            for t in c.get("teachers", []):
                t_name = t.get("display_name") or t.get("name")
                if t_name:
                    teachers.append(t_name)

            processed.append({
                "id": cid,
                "name": c.get("name", "").strip(),
                "course_code": c.get("course_code", "").strip(),
                "term_name": term_name,
                "workflow_state": workflow_state,
                "concluded": concluded,
                "is_favorite": is_fav,
                "is_active": is_active,
                "image_url": c.get("image_download_url"),
                "teachers": teachers,
                "created_at": c.get("created_at"),
            })

        # Ordenar: primero activos (con favoritos al frente), luego alfabéticamente
        processed.sort(
            key=lambda x: (
                0 if (x["is_active"] and x["is_favorite"]) else (1 if x["is_active"] else 2),
                x["name"].lower(),
            )
        )
        return processed

    def get_file_by_id(self, file_id: int) -> Optional[Dict[str, Any]]:
        """Obtiene metadatos y URL de descarga directa de un archivo individual por ID."""
        if file_id in self._file_cache:
            return self._file_cache[file_id]

        try:
            resp = self.session.get(
                f"{self.base_url}/api/v1/files/{file_id}",
                headers=self.get_headers(),
                timeout=12,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and "id" in data:
                    self._file_cache[file_id] = data
                    return data
        except Exception as e:
            logger.warning(f"Error resolviendo archivo individual {file_id}: {e}")
        return None

    def resolve_files_batch(self, file_ids: Iterable[int]) -> Dict[int, Dict[str, Any]]:
        """Resuelve múltiples archivos concurrentemente utilizando un pool de hilos."""
        unique_ids = set(file_ids)
        missing = [fid for fid in unique_ids if fid not in self._file_cache]
        if missing:
            with ThreadPoolExecutor(max_workers=10) as executor:
                list(executor.map(self.get_file_by_id, missing))
        return {fid: self._file_cache[fid] for fid in unique_ids if fid in self._file_cache}

    def discover_course_hidden_files(self, course_id: int, known_file_ids: Set[int]) -> List[Dict[str, Any]]:
        """
        Escanea páginas, tareas, discusiones y módulos para descubrir archivos
        que no aparecen en la pestaña de archivos (o cuando dicha pestaña está bloqueada).
        """
        found_sources: Dict[int, List[str]] = {}

        # 1. Escanear Módulos
        try:
            modules = self._paginate(
                f"{self.base_url}/api/v1/courses/{course_id}/modules",
                params={"include[]": ["items"]},
            )
            for m in modules:
                m_title = m.get("name", "Módulo")
                for it in m.get("items", []):
                    if it.get("type") == "File" and it.get("content_id"):
                        fid = int(it["content_id"])
                        found_sources.setdefault(fid, []).append(f"Módulo: {m_title}")
        except Exception as e:
            logger.warning(f"Error escaneando módulos para archivos ocultos: {e}")

        # 2. Escanear Tareas
        try:
            assignments = self._paginate(
                f"{self.base_url}/api/v1/courses/{course_id}/assignments",
                params={"include[]": ["attachments"]},
            )
            for a in assignments:
                a_name = a.get("name", "Tarea")
                for att in a.get("attachments", []):
                    if isinstance(att, dict) and "id" in att:
                        fid = int(att["id"])
                        found_sources.setdefault(fid, []).append(f"Tarea: {a_name}")
                        self._file_cache[fid] = att
                desc = a.get("description") or ""
                for m in re.finditer(r"/files/(\d+)", desc):
                    fid = int(m.group(1))
                    found_sources.setdefault(fid, []).append(f"Tarea: {a_name}")
        except Exception as e:
            logger.warning(f"Error escaneando tareas para archivos ocultos: {e}")

        # 3. Escanear Páginas
        try:
            pages = self._paginate(f"{self.base_url}/api/v1/courses/{course_id}/pages")

            def scan_page(p: Dict[str, Any]) -> Tuple[str, List[int]]:
                slug = p.get("url")
                title = p.get("title") or "Página"
                if not slug:
                    return title, []
                try:
                    r = self.session.get(
                        f"{self.base_url}/api/v1/courses/{course_id}/pages/{slug}",
                        headers=self.get_headers(),
                        timeout=10,
                    )
                    if r.status_code == 200:
                        body = r.json().get("body") or ""
                        fids = [int(m.group(1)) for m in re.finditer(r"/files/(\d+)", body)]
                        return title, fids
                except Exception:
                    pass
                return title, []

            if pages:
                with ThreadPoolExecutor(max_workers=10) as executor:
                    for title, fids in executor.map(scan_page, pages):
                        for fid in fids:
                            found_sources.setdefault(fid, []).append(f"Página: {title}")
        except Exception as e:
            logger.warning(f"Error escaneando páginas para archivos ocultos: {e}")

        new_fids = [fid for fid in found_sources.keys() if fid not in known_file_ids]
        if not new_fids:
            return []

        resolved_map = self.resolve_files_batch(new_fids)
        discovered_files = []
        for fid in new_fids:
            if fid not in resolved_map:
                continue
            f_obj = resolved_map[fid]
            srcs = list(dict.fromkeys(found_sources.get(fid, [])))
            src_label = srcs[0] if srcs else "Enlace del curso"
            if len(srcs) > 1:
                src_label += f" (+{len(srcs)-1})"

            discovered_files.append({
                "file_id": fid,
                "filename": f_obj.get("display_name") or f"archivo_{fid}",
                "size": f_obj.get("size", 0),
                "content_type": f_obj.get("content-type", "application/octet-stream"),
                "download_url": f_obj.get("url"),
                "updated_at": f_obj.get("updated_at"),
                "folder_id": f_obj.get("folder_id"),
                "is_hidden": True,
                "source": src_label,
            })

        return discovered_files

    def get_course_files_map(self, course_id: int) -> Dict[int, Dict[str, Any]]:
        """Obtiene un mapa {file_id: file_dict} de todos los archivos del curso."""
        files = self._paginate(
            f"{self.base_url}/api/v1/courses/{course_id}/files",
            params={"include[]": ["user"]},
        )
        files_map = {}
        for f in files:
            if isinstance(f, dict) and "id" in f:
                fid = f["id"]
                files_map[fid] = f
                self._file_cache[fid] = f
        return files_map

    def get_course_modules(self, course_id: int) -> List[Dict[str, Any]]:
        """Obtiene los módulos pedagógicos con sus items y archivos vinculados."""
        files_map = self.get_course_files_map(course_id)

        modules_data = self._paginate(
            f"{self.base_url}/api/v1/courses/{course_id}/modules",
            params={"include[]": ["items"]},
        )

        missing_fids = []
        for m in modules_data:
            for it in m.get("items", []):
                if it.get("type") == "File" and it.get("content_id"):
                    cid = int(it["content_id"])
                    if cid not in files_map:
                        missing_fids.append(cid)

        if missing_fids:
            resolved_missing = self.resolve_files_batch(missing_fids)
            files_map.update(resolved_missing)

        result_modules = []
        for m in modules_data:
            if not isinstance(m, dict) or "id" not in m:
                continue

            mod_id = m["id"]
            mod_name = m.get("name", f"Módulo {mod_id}").strip()
            items = []

            total_files = 0
            total_bytes = 0

            for it in m.get("items", []):
                item_type = it.get("type")
                item_title = it.get("title", "").strip()
                item_id = it.get("id")

                file_info = None
                if item_type == "File":
                    content_id = it.get("content_id")
                    if content_id and content_id in files_map:
                        f_obj = files_map[content_id]
                        size = f_obj.get("size", 0)
                        total_files += 1
                        total_bytes += size
                        file_info = {
                            "file_id": content_id,
                            "filename": f_obj.get("display_name") or item_title,
                            "size": size,
                            "content_type": f_obj.get("content-type", "application/octet-stream"),
                            "download_url": f_obj.get("url"),
                            "updated_at": f_obj.get("updated_at"),
                        }
                    else:
                        total_files += 1
                        file_info = {
                            "file_id": content_id,
                            "filename": item_title,
                            "size": 0,
                            "content_type": "application/octet-stream",
                            "download_url": it.get("url"),
                            "updated_at": None,
                        }

                items.append({
                    "id": item_id,
                    "title": item_title,
                    "type": item_type,
                    "position": it.get("position", 0),
                    "indent": it.get("indent", 0),
                    "html_url": it.get("html_url"),
                    "url": it.get("url"),
                    "external_url": it.get("external_url"),
                    "file": file_info,
                })

            result_modules.append({
                "id": mod_id,
                "name": mod_name,
                "position": m.get("position", 0),
                "items_count": len(items),
                "files_count": total_files,
                "total_bytes": total_bytes,
                "items": items,
            })

        return result_modules

    def get_course_folders_and_files(self, course_id: int) -> Dict[str, Any]:
        """Obtiene la jerarquía completa de carpetas y archivos nativos del curso, incluyendo archivos ocultos/enlazados."""
        folders = self._paginate(f"{self.base_url}/api/v1/courses/{course_id}/folders")
        files = self._paginate(f"{self.base_url}/api/v1/courses/{course_id}/files")

        folders_by_id = {}
        for fld in folders:
            if isinstance(fld, dict) and "id" in fld:
                folders_by_id[fld["id"]] = {
                    "id": fld["id"],
                    "name": fld.get("name", "Carpeta"),
                    "full_name": fld.get("full_name", ""),
                    "parent_folder_id": fld.get("parent_folder_id"),
                    "files_count": fld.get("files_count", 0),
                    "files": [],
                }

        known_file_ids: Set[int] = set()
        total_bytes = 0
        orphan_files = []
        for f in files:
            if not isinstance(f, dict) or "id" not in f:
                continue
            fid = f["id"]
            known_file_ids.add(fid)
            self._file_cache[fid] = f
            size = f.get("size", 0)
            total_bytes += size
            file_item = {
                "file_id": fid,
                "filename": f.get("display_name", "archivo"),
                "size": size,
                "content_type": f.get("content-type", "application/octet-stream"),
                "download_url": f.get("url"),
                "updated_at": f.get("updated_at"),
                "is_hidden": bool(f.get("hidden") or f.get("hidden_for_user")),
                "source": "Carpeta del curso",
            }
            fld_id = f.get("folder_id")
            if fld_id in folders_by_id:
                folders_by_id[fld_id]["files"].append(file_item)
            else:
                orphan_files.append(file_item)

        # Descubrimiento de archivos ocultos / enlazados en páginas o tareas
        discovered = self.discover_course_hidden_files(course_id, known_file_ids)
        hidden_folder_files = []

        for df in discovered:
            total_bytes += df["size"]
            fld_id = df.get("folder_id")
            if fld_id and fld_id in folders_by_id:
                folders_by_id[fld_id]["files"].append(df)
            else:
                hidden_folder_files.append(df)

        if hidden_folder_files:
            hidden_folder = {
                "id": -999,
                "name": "👁️ Archivos Enlazados y Ocultos",
                "full_name": "Archivos recuperados de Páginas, Tareas y Módulos",
                "parent_folder_id": None,
                "files_count": len(hidden_folder_files),
                "is_special": True,
                "files": hidden_folder_files,
            }
            folders_list = [hidden_folder] + list(folders_by_id.values())
        else:
            folders_list = list(folders_by_id.values())

        total_files_count = len(known_file_ids) + len(discovered)

        return {
            "folders": folders_list,
            "total_files": total_files_count,
            "total_bytes": total_bytes,
            "orphan_files": orphan_files,
            "hidden_files_count": len(discovered),
        }

    def get_course_assignments(self, course_id: int) -> List[Dict[str, Any]]:
        """Obtiene las tareas del curso con enunciados, materiales adjuntos y entregas del estudiante."""
        raw_assignments = self._paginate(
            f"{self.base_url}/api/v1/courses/{course_id}/assignments",
            params={
                "include[]": ["submission", "attachments"],
                "order_by": "due_at",
            },
        )

        embedded_fids: List[int] = []
        assignment_embedded_map: Dict[int, List[int]] = {}

        for a in raw_assignments:
            aid = a.get("id")
            desc = a.get("description") or ""
            fids = [int(m.group(1)) for m in re.finditer(r"/files/(\d+)", desc)]
            if fids:
                embedded_fids.extend(fids)
                assignment_embedded_map[aid] = fids

        resolved_files = self.resolve_files_batch(embedded_fids) if embedded_fids else {}

        assignments = []
        for a in raw_assignments:
            if not isinstance(a, dict) or "id" not in a:
                continue

            aid = a["id"]
            name = a.get("name", "Tarea").strip()
            desc = a.get("description") or ""
            due_at = a.get("due_at")
            points = a.get("points_possible")

            # 1. Materiales de la tarea (archivos del profesor)
            teacher_files: List[Dict[str, Any]] = []
            seen_fids = set()

            for att in a.get("attachments", []):
                fid = att.get("id")
                if fid and fid not in seen_fids:
                    seen_fids.add(fid)
                    teacher_files.append({
                        "file_id": fid,
                        "filename": att.get("display_name") or f"adjunto_{fid}",
                        "size": att.get("size", 0),
                        "content_type": att.get("content-type", "application/octet-stream"),
                        "download_url": att.get("url"),
                        "kind": "material",
                        "assignment_name": name,
                    })

            for fid in assignment_embedded_map.get(aid, []):
                if fid in resolved_files and fid not in seen_fids:
                    seen_fids.add(fid)
                    rf = resolved_files[fid]
                    teacher_files.append({
                        "file_id": fid,
                        "filename": rf.get("display_name") or f"material_{fid}",
                        "size": rf.get("size", 0),
                        "content_type": rf.get("content-type", "application/octet-stream"),
                        "download_url": rf.get("url"),
                        "kind": "material",
                        "assignment_name": name,
                    })

            # 2. Entregas del estudiante
            sub = a.get("submission") or {}
            sub_state = sub.get("workflow_state", "unsubmitted")
            submission_files: List[Dict[str, Any]] = []

            for satt in sub.get("attachments", []):
                sfid = satt.get("id")
                submission_files.append({
                    "file_id": sfid,
                    "filename": satt.get("display_name") or f"entrega_{sfid}",
                    "size": satt.get("size", 0),
                    "content_type": satt.get("content-type", "application/octet-stream"),
                    "download_url": satt.get("url"),
                    "kind": "submission",
                    "assignment_name": name,
                })

            if not due_at:
                group = "undated"
            else:
                try:
                    due_dt = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
                    now_dt = datetime.now(timezone.utc)
                    group = "upcoming" if due_dt > now_dt else "past"
                except Exception:
                    group = "past"

            assignments.append({
                "id": aid,
                "name": name,
                "due_at": due_at,
                "points_possible": points,
                "submission_types": a.get("submission_types", []),
                "html_url": a.get("html_url"),
                "has_submitted": sub_state in ("submitted", "graded"),
                "workflow_state": sub_state,
                "score": sub.get("score"),
                "grade": sub.get("grade"),
                "submitted_at": sub.get("submitted_at"),
                "group": group,
                "teacher_files": teacher_files,
                "submission_files": submission_files,
                "description_html": desc,
                "rubric": a.get("rubric"),
                "rubric_title": (a.get("rubric_settings") or {}).get("title"),
                "unlock_at": a.get("unlock_at"),
                "lock_at": a.get("lock_at"),
                "allowed_extensions": a.get("allowed_extensions") or [],
                "allowed_attempts": a.get("allowed_attempts"),
            })

        return assignments

    def get_full_course_plan(self, course_id: int, course_name: str) -> Dict[str, Any]:
        """
        Arma la lista de descarga de todo el curso: módulos, tareas, anuncios y archivos.
        El orden define la prioridad: un archivo que aparece en varias secciones
        se guarda solo en la primera (los duplicados por contenido los resuelve el downloader por hash).
        """
        items: List[Dict[str, Any]] = []
        errors: List[str] = []
        seen_fids: Set[int] = set()

        def add_file(f: Dict[str, Any], folder: str) -> None:
            fid = f.get("file_id")
            if not f.get("download_url") or (fid and fid in seen_fids):
                return
            if fid:
                seen_fids.add(fid)
            items.append({
                "file_id": fid,
                "filename": f.get("filename") or f"archivo_{fid}",
                "size": f.get("size", 0),
                "url": f["download_url"],
                "course_name": course_name,
                "folder_name": folder,
            })

        def add_html(filename: str, folder: str, title: str, meta: List[Tuple[str, Any]], body: str) -> None:
            content = _html_doc(title, [("Curso", course_name), *meta], body)
            items.append({
                "filename": f"{_seg(filename)}.html",
                "size": len(content.encode("utf-8")),
                "raw_content": content,
                "course_name": course_name,
                "folder_name": folder,
            })

        # 1. Módulos: archivos, páginas, discusiones, quizzes y enlaces externos
        try:
            jobs = []
            for m in self.get_course_modules(course_id):
                folder = f"Módulos/{_seg(m['name'])}"
                links = []
                for it in m["items"]:
                    if it["type"] == "File" and it["file"]:
                        add_file(it["file"], folder)
                    elif it["type"] in ("Page", "Discussion", "Quiz") and it.get("url"):
                        jobs.append((folder, it))
                    elif it["type"] in ("ExternalUrl", "ExternalTool") and (it.get("external_url") or it.get("html_url")):
                        links.append(it)
                if links:
                    body = "<ul>" + "".join(
                        f'<li><a href="{escape(l.get("external_url") or l["html_url"])}">{escape(l["title"])}</a></li>'
                        for l in links
                    ) + "</ul>"
                    add_html("Enlaces externos", folder, f"Enlaces: {m['name']}", [], body)

            def fetch_item(job):
                folder, it = job
                try:
                    r = self.session.get(it["url"], headers=self.get_headers(), timeout=15)
                    r.raise_for_status()
                    return folder, it, r.json(), None
                except Exception as e:
                    return folder, it, None, e

            embedded: List[int] = []
            with ThreadPoolExecutor(max_workers=10) as executor:
                for folder, it, data, err in executor.map(fetch_item, jobs):
                    if err:
                        errors.append(f"{it['type']} '{it['title']}': {err}")
                        continue
                    body = data.get("body") or data.get("message") or data.get("description") or ""
                    meta = []
                    if it["type"] == "Quiz":
                        meta = [("Puntaje", data.get("points_possible")), ("Preguntas", data.get("question_count")),
                                ("Límite de tiempo (min)", data.get("time_limit")), ("Fecha de entrega", _fmt_date(data.get("due_at")))]
                    add_html(it["title"], folder, it["title"], meta, body)
                    for att in data.get("attachments") or []:
                        add_file(_file_entry(att), folder)
                    embedded.extend(int(x.group(1)) for x in re.finditer(r"/files/(\d+)", body))
            for f_obj in self.resolve_files_batch(embedded).values():
                add_file(_file_entry(f_obj), "Módulos/Archivos enlazados")
        except Exception as e:
            logger.warning(f"Error armando módulos del curso {course_id}: {e}")
            errors.append(f"Módulos: {e}")

        # 2. Tareas: enunciado, materiales del profesor y entregas propias
        try:
            for a in self.get_course_assignments(course_id):
                folder = f"Tareas/{_seg(a['name'])}"
                body = (a.get("description_html") or "") + _rubric_html(a.get("rubric"), a.get("rubric_title") or "")
                if body.strip():
                    meta = [
                        ("Fecha de entrega", _fmt_date(a["due_at"]) or "Sin fecha"),
                        ("Disponible desde", _fmt_date(a.get("unlock_at"))),
                        ("Disponible hasta", _fmt_date(a.get("lock_at"))),
                        ("Puntaje", a["points_possible"]),
                        ("Tipo de entrega", ", ".join(a.get("submission_types") or [])),
                        ("Extensiones permitidas", ", ".join(a.get("allowed_extensions") or [])),
                        ("Intentos permitidos", a.get("allowed_attempts")),
                        ("Mi nota", a.get("grade")),
                        ("Enlace en Canvas", a.get("html_url")),
                    ]
                    add_html(f"{a['name']}_Instrucciones", folder, a["name"], meta, body)
                for f in a["teacher_files"]:
                    add_file(f, folder)
                for f in a["submission_files"]:
                    add_file(f, f"{folder}/Mi entrega")
        except Exception as e:
            logger.warning(f"Error armando tareas del curso {course_id}: {e}")
            errors.append(f"Tareas: {e}")

        # 3. Anuncios: texto, adjuntos y archivos enlazados en el mensaje
        try:
            announcements = self._paginate(
                f"{self.base_url}/api/v1/courses/{course_id}/discussion_topics",
                params={"only_announcements": "true"},
            )
            embedded: List[int] = []
            for an in announcements:
                title = an.get("title") or "Anuncio"
                posted = an.get("posted_at") or an.get("created_at")
                msg = an.get("message") or ""
                author = (an.get("author") or {}).get("display_name")
                add_html(f"{(posted or '')[:10]} {title}".strip(), "Anuncios", title,
                         [("Publicado", _fmt_date(posted)), ("Autor", author)], msg)
                for att in an.get("attachments") or []:
                    add_file(_file_entry(att), "Anuncios/Adjuntos")
                embedded.extend(int(m.group(1)) for m in re.finditer(r"/files/(\d+)", msg))
            for f_obj in self.resolve_files_batch(embedded).values():
                add_file(_file_entry(f_obj), "Anuncios/Adjuntos")
        except Exception as e:
            logger.warning(f"Error armando anuncios del curso {course_id}: {e}")
            errors.append(f"Anuncios: {e}")

        # 4. Archivos: árbol de carpetas del curso + enlazados/ocultos
        try:
            data = self.get_course_folders_and_files(course_id)
            for fld in data["folders"]:
                if fld.get("is_special"):
                    folder = "Archivos/Enlazados"
                else:
                    # full_name = "course files/Semana 1/..." -> "Archivos/Semana 1/..."
                    parts = (fld.get("full_name") or "").split("/")[1:]
                    folder = "/".join(["Archivos", *(_seg(p) for p in parts)])
                for f in fld["files"]:
                    add_file(f, folder)
            for f in data["orphan_files"]:
                add_file(f, "Archivos")
        except Exception as e:
            logger.warning(f"Error armando archivos del curso {course_id}: {e}")
            errors.append(f"Archivos: {e}")

        return {"items": items, "errors": errors}


# Instancia singleton para la aplicación
canvas_client = CanvasClient()
