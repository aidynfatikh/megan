import pytest

from backend.db import BusyError, ConflictError
from backend.schemas import Report

pytestmark = pytest.mark.integration


async def test_committed_job_and_report_survive_new_connections(repository, new_job):
    await repository.create(new_job)
    new_job.status = "done"
    new_job.report = Report(title="Смета / бюджет")
    await repository.save(new_job, new_revision=True)
    actual = await repository.get(new_job.id)
    assert actual.status == "done"
    assert actual.report.title == "Смета / бюджет"
    assert actual.report_revision == 1
    async with repository.pool.connection() as conn:
        row = await (
            await conn.execute(
                "SELECT payload FROM report_revisions WHERE job_id=%s AND revision=1", (new_job.id,)
            )
        ).fetchone()
        assert row["payload"]["title"] == "Смета / бюджет"


async def test_database_prevents_two_active_jobs(repository, new_job):
    from uuid import uuid4

    await repository.create(new_job)
    other = new_job.model_copy(update={"id": uuid4()})
    with pytest.raises(BusyError):
        await repository.create(other)
    new_job.status = "failed"
    await repository.save(new_job)
    await repository.create(other)


async def test_recovery_preserves_transcript_and_marks_interrupted(repository, new_job):
    from backend.schemas import Segment

    new_job.status = "running"
    new_job.segments = [Segment(id="S1", start=0, end=1, text="Hello")]
    await repository.create(new_job)
    await repository.recover()
    actual = await repository.get(new_job.id)
    assert actual.status == "interrupted"
    assert actual.segments == new_job.segments
    assert actual.error.retryable


async def test_stale_edit_cannot_overwrite_new_revision(repository, new_job):
    new_job.status = "done"
    new_job.report = Report(title="Original")
    await repository.create(new_job)
    await repository.save(new_job, new_revision=True)
    stale = await repository.get(new_job.id)
    fresh = await repository.get(new_job.id)
    fresh.report.title = "Fresh"
    await repository.save(fresh, new_revision=True, expected_revision=1)
    stale.report.title = "Stale"
    with pytest.raises(ConflictError):
        await repository.save(stale, new_revision=True, expected_revision=1)
    assert (await repository.get(new_job.id)).report.title == "Fresh"
