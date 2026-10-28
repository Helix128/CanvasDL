"""CanvasDL command line interface. Output is JSON for easy agent use."""

import argparse
import asyncio
import json
import sys

from app.bridge import download_course, download_status, download_items
from app.canvas_api import canvas_client


def emit(data):
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(prog="canvasdl", description="CanvasDL local Canvas CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Verify Canvas authentication")
    sub.add_parser("courses", help="List courses")
    for cmd in ("modules", "files", "assignments", "plan", "download"):
        p = sub.add_parser(cmd)
        p.add_argument("course_id", type=int)
    p = sub.add_parser("download-files", help="Download selected files from course plan")
    p.add_argument("course_id", type=int)
    p.add_argument("file_ids", nargs="+", type=int)
    sub.add_parser("downloads", help="Show download queue")
    args = parser.parse_args()
    try:
        if args.command == "status":
            result = canvas_client.verify_auth()
        elif args.command == "courses":
            result = canvas_client.get_courses()
        elif args.command == "modules":
            result = canvas_client.get_course_modules(args.course_id)
        elif args.command == "files":
            result = canvas_client.get_course_folders_and_files(args.course_id)
        elif args.command == "assignments":
            result = canvas_client.get_course_assignments(args.course_id)
        elif args.command == "plan":
            result = canvas_client.get_full_course_plan(args.course_id, next(
                c["name"] for c in canvas_client.get_courses() if int(c["id"]) == args.course_id))
        elif args.command == "download":
            result = asyncio.run(download_course(args.course_id))
        elif args.command == "download-files":
            name = next(c["name"] for c in canvas_client.get_courses() if int(c["id"]) == args.course_id)
            plan = canvas_client.get_full_course_plan(args.course_id, name)
            selected = [i for i in plan["items"] if i.get("file_id") in set(args.file_ids)]
            result = asyncio.run(download_items(selected))
        else:
            result = download_status()
        emit(result)
    except (Exception, StopIteration) as exc:
        print(f"canvasdl: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
