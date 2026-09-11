import pytest

from backend.db import BusyError, ConflictError
from backend.schemas import Report, Segment, Speaker

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


async def stored_speakers(repository, job_id):
    async with repository.pool.connection() as conn:
        row = await (
            await conn.execute("SELECT document->'speakers' AS s FROM jobs WHERE id=%s", (job_id,))
        ).fetchone()
    return [(s["id"], s["name"], s["name_source"]) for s in row["s"]]


async def replay_speaker_backfill(repository):
    from pathlib import Path

    import backend.db

    sql = (
        Path(backend.db.__file__).parent / "migrations" / "003_drop_unattributed_speakers.sql"
    ).read_text()
    async with repository.pool.connection() as conn:
        await conn.execute(sql)


async def test_backfill_drops_stored_voices_that_hold_no_transcript_text(repository, new_job):
    # A 0.48 s diarizer false alarm in a silent gap named a second participant in a monologue.
    new_job.segments = [
        Segment(id="S1", start=0, end=4, text="По кредитованию юрлиц.", speaker_id="speaker_0"),
        Segment(
            id="S2", start=5, end=9, text="Мы участвуем в госпрограммах.", speaker_id="speaker_0"
        ),
    ]
    new_job.speakers = [
        Speaker(id="speaker_0", name="Speaker 1"),
        Speaker(id="speaker_1", name="Speaker 2"),
    ]
    new_job.diarization_status = "done"
    await repository.create(new_job)
    await replay_speaker_backfill(repository)
    assert await stored_speakers(repository, new_job.id) == [
        ("speaker_0", "Speaker 1", "anonymous")
    ]
    assert [s.speaker_id for s in (await repository.get(new_job.id)).segments] == [
        "speaker_0",
        "speaker_0",
    ]


async def test_backfill_closes_the_numbering_gap_and_keeps_edited_names(repository, new_job):
    # The dropped voice was listed first, so the surviving anonymous one must become Speaker 1.
    new_job.segments = [
        Segment(id="S1", start=0, end=4, text="Первая реплика.", speaker_id="speaker_1"),
        Segment(id="S2", start=5, end=9, text="Вторая реплика.", speaker_id="speaker_2"),
    ]
    new_job.speakers = [
        Speaker(id="speaker_0", name="Speaker 1"),
        Speaker(id="speaker_1", name="Speaker 2"),
        Speaker(id="speaker_2", name="Айдын", name_source="user_edit"),
    ]
    new_job.diarization_status = "done"
    await repository.create(new_job)
    await replay_speaker_backfill(repository)
    assert await stored_speakers(repository, new_job.id) == [
        ("speaker_1", "Speaker 1", "anonymous"),
        ("speaker_2", "Айдын", "user_edit"),
    ]


async def test_backfill_leaves_a_healthy_speaker_list_and_a_disabled_job_alone(repository, new_job):
    from uuid import uuid4

    new_job.segments = [
        Segment(id="S1", start=0, end=4, text="Первая реплика.", speaker_id="speaker_0"),
        Segment(id="S2", start=5, end=9, text="Вторая реплика.", speaker_id="speaker_1"),
    ]
    new_job.speakers = [
        Speaker(id="speaker_0", name="Speaker 1"),
        Speaker(id="speaker_1", name="Speaker 2"),
    ]
    new_job.diarization_status = "done"
    new_job.status = "done"
    await repository.create(new_job)
    without = new_job.model_copy(
        update={"id": uuid4(), "speakers": [], "diarization_status": "disabled", "status": "done"}
    )
    without.segments = [s.model_copy(update={"speaker_id": None}) for s in new_job.segments]
    await repository.create(without)
    await replay_speaker_backfill(repository)
    assert await stored_speakers(repository, new_job.id) == [
        ("speaker_0", "Speaker 1", "anonymous"),
        ("speaker_1", "Speaker 2", "anonymous"),
    ]
    assert await stored_speakers(repository, without.id) == []
