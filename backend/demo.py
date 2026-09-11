"""Import curated, already-processed recordings once; preserve subsequent user edits."""

import shutil
from pathlib import Path

from psycopg.types.json import Jsonb

from backend.schemas import Job


async def seed_demo(repo, source: Path, data: Path):
    for path in sorted(source.glob("*/job.json")):
        job = Job.model_validate_json(path.read_text())
        if job.status != "done" or not job.report or not job.provenance.demo:
            raise ValueError("Demo seed requires a completed, explicitly labelled recording")
        audio = path.with_name("recording.wav")
        if not audio.is_file():
            raise ValueError("Demo recording is missing")
        directory = data / "jobs" / str(job.id)
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / "normalized.wav"
        if not destination.exists():
            temporary = directory / "demo-audio.tmp"
            shutil.copyfile(audio, temporary)
            temporary.replace(destination)
        async with repo.pool.connection() as conn:
            row = await (
                await conn.execute(
                    "INSERT INTO jobs(id,status,revision,document,created_at) VALUES (%s,%s,%s,%s,%s) "
                    "ON CONFLICT (id) DO NOTHING RETURNING id",
                    (
                        job.id,
                        job.status,
                        job.report_revision,
                        Jsonb(job.model_dump(mode="json")),
                        job.created_at,
                    ),
                )
            ).fetchone()
            if row:
                await conn.execute(
                    "INSERT INTO report_revisions(job_id,revision,payload) VALUES (%s,%s,%s)",
                    (job.id, job.report_revision, Jsonb(job.report.model_dump(mode="json"))),
                )
