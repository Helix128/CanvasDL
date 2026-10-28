"""MCP server exposing CanvasDL's Canvas and download features (stdio & remote SSE/HTTP)."""

import argparse
import hmac
import logging
import os
from pathlib import Path
from typing import Any
import urllib.parse

from mcp.server.fastmcp import FastMCP
from starlette.responses import PlainTextResponse

from app.bridge import (
    copy_cached_files,
    download_status,
    list_cached_files,
    start_course_download,
    start_download_items,
)
from app.canvas_api import _file_entry, canvas_client
from app.config import get_download_path

logger = logging.getLogger("mcp_server")

mcp = FastMCP("CanvasDL")


@mcp.tool()
def canvas_status() -> dict:
    """Verify Canvas token and return current user."""
    return canvas_client.verify_auth()


@mcp.tool()
def list_courses() -> list[dict]:
    """List accessible Canvas courses, active courses first."""
    return canvas_client.get_courses()


@mcp.tool()
def list_modules(course_id: int) -> list[dict]:
    """List course modules and their items."""
    return canvas_client.get_course_modules(course_id)


@mcp.tool()
def list_files(course_id: int) -> dict:
    """List course folders, files, and linked or hidden files."""
    return canvas_client.get_course_folders_and_files(course_id)


@mcp.tool()
def list_assignments(course_id: int) -> list[dict]:
    """List assignments, teacher attachments, and submitted files."""
    return canvas_client.get_course_assignments(course_id)


@mcp.tool()
def course_download_plan(course_id: int) -> dict:
    """Build complete local download plan for course materials."""
    course = next((c for c in canvas_client.get_courses() if int(c["id"]) == course_id), None)
    if course is None:
        raise ValueError(f"Curso {course_id} no encontrado o no accesible")
    return canvas_client.get_full_course_plan(course_id, course["name"])


@mcp.tool()
def get_file_info(file_id: int) -> dict:
    """Get metadata and download URL for a specific file by file_id (useful for Claude Web)."""
    f = canvas_client.resolve_file(file_id)
    if not f:
        raise ValueError(f"Archivo {file_id} no encontrado o inaccesible")
    return _file_entry(f)


@mcp.tool()
async def download_course_materials(course_id: int, destination_dir: str | None = None) -> dict:
    """Download course materials to destination_dir, or CanvasDL's cache when omitted."""
    return await start_course_download(course_id, destination_dir)


@mcp.tool()
async def download_selected_files(course_id: int, file_ids: list[int], destination_dir: str | None = None) -> dict:
    """Start download of selected Canvas file IDs found in course download plan."""
    course = next((c for c in canvas_client.get_courses() if int(c["id"]) == course_id), None)
    if course is None:
        raise ValueError(f"Curso {course_id} no encontrado o no accesible")
    plan = canvas_client.get_full_course_plan(course_id, course["name"])
    wanted = set(file_ids)
    items = [item for item in plan["items"] if item.get("file_id") in wanted]
    result = await start_download_items(items, destination_dir)
    destination = Path(destination_dir).expanduser().resolve() if destination_dir else get_download_path()
    return {**result, "course_id": course_id, "download_dir": str(destination), "plan_errors": plan["errors"]}


@mcp.tool()
def canvas_get(path: str, params: dict | None = None, max_items: int = 500) -> Any:
    """Read ANY Canvas REST endpoint (GET only, follows pagination, list results capped at max_items).

    path must start with /api/v1/. params are query params; repeat keys as lists, e.g.
    {"include[]": ["syllabus_body", "term"]}. Common paths ({id} = course id):
    /api/v1/users/self, /api/v1/users/self/profile, /api/v1/users/self/todo,
    /api/v1/users/self/upcoming_events, /api/v1/users/self/files, /api/v1/users/self/enrollments,
    /api/v1/planner/items, /api/v1/calendar_events?context_codes[]=course_{id},
    /api/v1/announcements?context_codes[]=course_{id}, /api/v1/conversations, /api/v1/conversations/{cid},
    /api/v1/courses/{id} (+include[]=syllabus_body), /api/v1/courses/{id}/tabs,
    /api/v1/courses/{id}/pages, /api/v1/courses/{id}/pages/{url_or_id},
    /api/v1/courses/{id}/discussion_topics, /api/v1/courses/{id}/discussion_topics/{tid}/view,
    /api/v1/courses/{id}/quizzes, /api/v1/courses/{id}/quizzes/{qid}/submissions,
    /api/v1/courses/{id}/assignments, /api/v1/courses/{id}/assignment_groups,
    /api/v1/courses/{id}/assignments/{aid}/submissions/self (+include[]=submission_comments,rubric_assessment),
    /api/v1/courses/{id}/students/submissions?student_ids[]=self, /api/v1/courses/{id}/enrollments?user_id=self (grades),
    /api/v1/courses/{id}/rubrics, /api/v1/courses/{id}/modules, /api/v1/courses/{id}/modules/{mid}/items,
    /api/v1/courses/{id}/files, /api/v1/courses/{id}/folders, /api/v1/folders/{fid}/files, /api/v1/files/{file_id},
    /api/v1/courses/{id}/users, /api/v1/courses/{id}/groups, /api/v1/users/self/groups,
    /api/v1/courses/{id}/outcome_groups, /api/v1/courses/{id}/front_page, /api/v1/courses/{id}/activity_stream.
    Use download_files to save any file_id found here.
    """
    return canvas_client.api_get(path, params, max_items)


@mcp.tool()
async def download_files(file_ids: list[int], destination_dir: str | None = None) -> dict:
    """Download any Canvas file IDs (course, submission, attachment, inbox or user files) by ID."""
    files = canvas_client.resolve_files_batch(file_ids)
    missing = [fid for fid in file_ids if fid not in files]
    items = [{**_file_entry(f), "course_name": "Archivos", "folder_name": "General"} for f in files.values()]
    result = await start_download_items(items, destination_dir)
    destination = Path(destination_dir).expanduser().resolve() if destination_dir else get_download_path()
    return {**result, "download_dir": str(destination), "unresolved_file_ids": missing}


@mcp.tool()
def cached_files() -> list[dict]:
    """List files in CanvasDL's download cache using paths relative to the cache."""
    return list_cached_files()


@mcp.tool()
def copy_cached_files_to(paths: list[str], destination_dir: str) -> dict:
    """Copy listed cache paths to a local folder, preserving folders and avoiding overwrite."""
    return copy_cached_files(paths, destination_dir)


@mcp.tool()
def download_queue() -> dict:
    """Return current local download status and configured folder."""
    return download_status()


@mcp.tool()
def cancel_downloads() -> dict:
    """Cancel queued and active local downloads."""
    from app.downloader import bulk_downloader
    bulk_downloader.cancel_all()
    return {"success": True, "downloads": bulk_downloader.get_status()}


class AuthTokenMiddleware:
    """Enforce token authentication for HTTP/SSE endpoints (ISO 27001 8.24 / SOC 2 CC6.1)."""

    def __init__(self, app, expected_token: str):
        self.app = app
        self.expected_token = expected_token

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            auth_val = headers.get(b"authorization", b"").decode("utf-8")
            token = None
            if auth_val.lower().startswith("bearer "):
                token = auth_val[7:].strip()
            if not token:
                query_string = scope.get("query_string", b"").decode("utf-8")
                params = urllib.parse.parse_qs(query_string)
                token = params.get("token", [None])[0]

            if not token or not hmac.compare_digest(token, self.expected_token):
                res = PlainTextResponse(
                    "Unauthorized: Valid Bearer token required in Authorization header or ?token= parameter\n",
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await res(scope, receive, send)
                return
        await self.app(scope, receive, send)


def main():
    parser = argparse.ArgumentParser(description="CanvasDL MCP Server (stdio, SSE & Streamable-HTTP)")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default=os.environ.get("MCP_TRANSPORT", "stdio"),
        help="Transport protocol to use: 'stdio' (Claude Code/Desktop) or 'sse'/'streamable-http' (Claude Web) (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("MCP_HOST", "127.0.0.1"),
        help="Host to bind for HTTP/SSE (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MCP_PORT", "8000")),
        help="Port to bind for HTTP/SSE (default: 8000)",
    )
    parser.add_argument(
        "--auth-token",
        default=os.environ.get("MCP_AUTH_TOKEN"),
        help="Security Bearer token required to access remote HTTP/SSE endpoints (ISO/SOC 2 compliance)",
    )
    parser.add_argument(
        "--allowed-hosts",
        default=os.environ.get("MCP_ALLOWED_HOSTS"),
        help="Allowed hosts/domains for DNS rebinding protection, e.g. '*.trycloudflare.com,localhost' or '*' (default: localhost)",
    )

    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
        return

    # Transport is SSE or Streamable-HTTP (e.g. for Claude Web or remote clients)
    import uvicorn

    mcp.settings.host = args.host
    mcp.settings.port = args.port

    if args.allowed_hosts:
        if args.allowed_hosts == "*":
            mcp.settings.transport_security.enable_dns_rebinding_protection = False
        else:
            hosts = [h.strip() for h in args.allowed_hosts.split(",") if h.strip()]
            mcp.settings.transport_security.allowed_hosts.extend(hosts)
            for h in hosts:
                mcp.settings.transport_security.allowed_origins.extend([f"https://{h}", f"http://{h}"])
    elif args.auth_token:
        # Si hay token de autenticación fuerte configurado, permitimos conexiones desde túneles (Cloudflare, ngrok)
        mcp.settings.transport_security.enable_dns_rebinding_protection = False

    if args.transport == "sse":
        starlette_app = mcp.sse_app()
    else:
        starlette_app = mcp.streamable_http_app()

    if args.auth_token:
        starlette_app = AuthTokenMiddleware(starlette_app, args.auth_token)
    elif args.host != "127.0.0.1":
        logger.warning(
            "ALERTA DE SEGURIDAD (ISO 27001 / SOC 2): El servidor MCP se está ejecutando en %s sin --auth-token. "
            "Cualquier cliente en la red podrá acceder a tus herramientas de Canvas.",
            args.host,
        )

    print(f"CanvasDL MCP Server running on {args.transport.upper()} at http://{args.host}:{args.port}")
    if args.auth_token:
        print("✓ Autenticación Bearer activa (--auth-token configurado)")

    uvicorn.run(
        starlette_app,
        host=args.host,
        port=args.port,
        log_level=mcp.settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
