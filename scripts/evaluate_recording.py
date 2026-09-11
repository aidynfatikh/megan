"""Submit one local recording and retain its unedited report, exports, and timing receipt."""

import argparse
import hashlib
import json
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from backend.config import is_loopback


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path)
    parser.add_argument(
        "output", type=Path, help="A new directory; existing results are never replaced"
    )
    parser.add_argument("--language", choices=["en", "ru", "kk"], default="ru")
    parser.add_argument("--meeting-date", type=date.fromisoformat)
    parser.add_argument("--api", default="http://127.0.0.1:8765")
    args = parser.parse_args()
    url = urlsplit(args.api)
    if url.scheme != "http" or not is_loopback(url.hostname) or url.username or url.password:
        parser.error("Use a local loopback HTTP API")
    if not args.audio.is_file():
        parser.error("Audio file does not exist")
    args.output.mkdir(parents=True, exist_ok=False)

    def save(name, data):
        (args.output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    with args.audio.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    receipt = {
        "audio": args.audio.name,
        "audio_sha256": digest,
        "language": args.language,
        "meeting_date": str(args.meeting_date) if args.meeting_date else None,
    }
    save("receipt.json", receipt)
    with httpx.Client(base_url=args.api, timeout=60, trust_env=False) as client:
        response = client.get("/api/health")
        response.raise_for_status()
        health = response.json()
        if not health["ready"] or health["busy"]:
            raise SystemExit("API must be ready and idle; do not overlap direct model tests")
        receipt["health_before"] = health
        data = {"report_language": args.language}
        if args.meeting_date:
            data["meeting_date"] = args.meeting_date.isoformat()
        started = time.monotonic()
        with args.audio.open("rb") as audio:
            response = client.post("/api/jobs", files={"file": (args.audio.name, audio)}, data=data)
        response.raise_for_status()
        job_id = response.json()["id"]
        receipt.update(job_id=job_id, stages=[])
        save("receipt.json", receipt)
        print(f"Job {job_id}", flush=True)
        previous = None
        while True:
            response = client.get(f"/api/jobs/{job_id}")
            response.raise_for_status()
            job = response.json()
            elapsed = round(time.monotonic() - started, 3)
            if job["stage"] != previous:
                previous = job["stage"]
                receipt["stages"].append({"stage": previous, "elapsed_sec": elapsed})
                print(f"{previous}: {elapsed}s", flush=True)
            if job["status"] in {"done", "failed", "interrupted"}:
                break
            if elapsed > 1800:
                raise TimeoutError(f"Job {job_id} still running; inspect it before retrying")
            time.sleep(1)
        save("job.json", job)
        receipt.update(
            status=job["status"], elapsed_sec=elapsed, timings=job.get("timings"), exports={}
        )
        save("receipt.json", receipt)
        if job["status"] != "done":
            raise SystemExit(f"Job {job['status']}: {job.get('error')}")
        for extension in ("json", "csv", "ics"):
            response = client.get(f"/api/jobs/{job_id}/export", params={"format": extension})
            response.raise_for_status()
            (args.output / f"report.{extension}").write_bytes(response.content)
            receipt["exports"][extension] = {
                "status": response.status_code,
                "bytes": len(response.content),
            }
        response = client.get(f"/api/jobs/{job_id}/audio", headers={"Range": "bytes=0-63"})
        response.raise_for_status()
        receipt["audio_range"] = {"status": response.status_code, "bytes": len(response.content)}
        save("receipt.json", receipt)
        print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
