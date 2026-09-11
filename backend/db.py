from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from backend.schemas import Job, JobError


class BusyError(Exception):
    pass


class ConflictError(Exception):
    pass


class Repository:
    def __init__(self, url: str):
        self.url = url
        self.pool = AsyncConnectionPool(
            url,
            min_size=1,
            max_size=4,
            open=False,
            timeout=5,
            kwargs={"row_factory": dict_row, "connect_timeout": 3},
        )
        self.lease = None

    async def open(self):
        await self.pool.open()
        try:
            await self.pool.wait(timeout=5)
        except Exception:
            await self.pool.close()
            raise

    async def close(self):
        if self.lease:
            await self.lease.close()
        await self.pool.close()

    async def acquire_runner(self):
        self.lease = await psycopg.AsyncConnection.connect(self.url, autocommit=True)
        row = await (await self.lease.execute("SELECT pg_try_advisory_lock(7263401001)")).fetchone()
        if not row[0]:
            await self.lease.close()
            self.lease = None
            raise BusyError("Another Megan runner is using this database. Run one API process.")

    async def migrate(self):
        async with self.pool.connection() as conn:
            await conn.execute("SELECT pg_advisory_xact_lock(7263401002)")
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
            )
            applied = {
                row["name"]
                for row in await (
                    await conn.execute("SELECT name FROM schema_migrations")
                ).fetchall()
            }
            for path in sorted((Path(__file__).parent / "migrations").glob("*.sql")):
                if path.name not in applied:
                    await conn.execute(path.read_text())
                    await conn.execute(
                        "INSERT INTO schema_migrations(name) VALUES (%s)", (path.name,)
                    )

    async def healthy(self):
        async with self.pool.connection() as conn:
            await conn.execute("SELECT 1")
        return True

    async def create(self, job: Job):
        try:
            async with self.pool.connection() as conn:
                await conn.execute(
                    "INSERT INTO jobs(id,status,document,created_at) VALUES (%s,%s,%s,%s)",
                    (job.id, job.status, Jsonb(job.model_dump(mode="json")), job.created_at),
                )
        except psycopg.errors.UniqueViolation as exc:
            raise BusyError("A meeting is already being processed") from exc

    async def get(self, job_id: UUID) -> Job | None:
        async with self.pool.connection() as conn:
            row = await (
                await conn.execute("SELECT document FROM jobs WHERE id=%s", (job_id,))
            ).fetchone()
        return Job.model_validate(row["document"]) if row else None

    async def list(self, limit=30):
        async with self.pool.connection() as conn:
            rows = await (
                await conn.execute(
                    "SELECT document FROM jobs ORDER BY created_at DESC LIMIT %s", (limit,)
                )
            ).fetchall()
        return [Job.model_validate(row["document"]) for row in rows]

    async def save(self, job: Job, *, new_revision=False, expected_revision=None):
        async with self.pool.connection() as conn:
            row = await (
                await conn.execute("SELECT revision FROM jobs WHERE id=%s FOR UPDATE", (job.id,))
            ).fetchone()
            if row is None:
                raise KeyError(job.id)
            if expected_revision is not None and row["revision"] != expected_revision:
                raise ConflictError("This report changed. Reload before saving your edit.")
            revision = row["revision"] + (1 if new_revision else 0)
            job.report_revision = revision
            job.updated_at = datetime.now(UTC)
            await conn.execute(
                "UPDATE jobs SET status=%s, revision=%s, document=%s, updated_at=%s WHERE id=%s",
                (job.status, revision, Jsonb(job.model_dump(mode="json")), job.updated_at, job.id),
            )
            if new_revision and job.report:
                await conn.execute(
                    "INSERT INTO report_revisions(job_id,revision,payload) VALUES (%s,%s,%s)",
                    (job.id, revision, Jsonb(job.report.model_dump(mode="json"))),
                )

    async def recover(self):
        async with self.pool.connection() as conn:
            rows = await (
                await conn.execute("SELECT document FROM jobs WHERE status IN ('queued','running')")
            ).fetchall()
        for row in rows:
            job = Job.model_validate(row["document"])
            job.error = JobError(
                code="interrupted",
                message="Processing was interrupted. Retry this meeting.",
                stage=job.stage,
            )
            job.status = "interrupted"
            await self.save(job)
