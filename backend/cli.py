"""Local CLI: diagnose setup, serve the application, or process through its API."""

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from backend.config import Settings, is_loopback
from backend.runtime import preflight


async def process_file(
    recording: Path, meeting_date: date | None, language: str, output: Path, api_url: str
):
    url = urlsplit(api_url)
    if (
        url.scheme != "http"
        or not is_loopback(url.hostname)
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.path not in ("", "/")
    ):
        raise ValueError("Use a loopback HTTP API URL, such as http://127.0.0.1:8000")
    data = {"report_language": language}
    if meeting_date:
        data["meeting_date"] = meeting_date.isoformat()
    async with httpx.AsyncClient(
        base_url=api_url, timeout=60, trust_env=False, follow_redirects=False
    ) as client:
        with recording.open("rb") as audio:
            response = await client.post(
                "/api/jobs", files={"file": (recording.name, audio)}, data=data
            )
        response.raise_for_status()
        job_id = response.json()["id"]
        print(f"Job {job_id}", file=sys.stderr, flush=True)
        last = None
        while True:
            response = await client.get(f"/api/jobs/{job_id}")
            response.raise_for_status()
            job = response.json()
            if job["stage"] != last:
                last = job["stage"]
                print(last, file=sys.stderr, flush=True)
            if job["status"] == "done":
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(
                    json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                return job
            if job["status"] in ("failed", "interrupted"):
                raise RuntimeError(
                    f"Job {job_id}: {job.get('error', {}).get('message', 'Processing failed')}. Retry in the browser."
                )
            await asyncio.sleep(2)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="megan")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "preflight", help="Check local services and artifacts without loading models"
    )
    serve = commands.add_parser("serve", help="Serve the built app locally with one worker")
    serve.add_argument("--port", type=int, default=8000)
    process = commands.add_parser("process", help="Upload a recording to the running local app")
    process.add_argument("recording", type=Path)
    process.add_argument("--date", type=date.fromisoformat)
    process.add_argument("--language", choices=["ru", "kk", "en"], default="ru")
    process.add_argument("--output", type=Path, default=Path("data/report.json"))
    process.add_argument("--api", default="http://127.0.0.1:8000")
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            result = asyncio.run(preflight(Settings()))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["ready"] else 1
        if args.command == "serve":
            import uvicorn

            uvicorn.run("backend.main:app", host="127.0.0.1", port=args.port, workers=1)
        else:
            asyncio.run(
                process_file(args.recording, args.date, args.language, args.output, args.api)
            )
        return 0
    except (OSError, ValueError, RuntimeError, httpx.HTTPError) as exc:
        print(f"Megan: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
