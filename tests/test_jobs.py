import asyncio

import pytest

from backend.config import Settings
from backend.db import BusyError
from backend.schemas import Report, Segment
from backend.worker import Runner

pytestmark = pytest.mark.integration


class ControlledPipeline:
    def __init__(self):
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.fail = False

    async def run(self, job, directory, checkpoint):
        job.segments = [Segment(id="S1", start=0, end=2, text="We discussed the budget.")]
        await checkpoint("analyze")
        self.entered.set()
        await self.release.wait()
        if self.fail:
            raise RuntimeError("test model failure")
        return Report(title="Budget discussion")


async def test_single_job_and_failure_retry_keep_transcript(repository, new_job, tmp_path):
    pipeline = ControlledPipeline()
    runner = Runner(repository, Settings(_env_file=None, data_dir=tmp_path), pipeline)
    await repository.create(new_job)
    runner.start(new_job)
    await asyncio.wait_for(pipeline.entered.wait(), 2)
    assert runner.busy
    with pytest.raises(BusyError):
        runner.reserve()
    pipeline.fail = True
    pipeline.release.set()
    await runner.wait()
    saved = await repository.get(new_job.id)
    assert saved.status == "failed"
    assert saved.segments[0].text == "We discussed the budget."
    assert saved.error.stage == "analyze"
    assert not runner.busy
    pipeline.fail = False
    await runner.retry(saved.id)
    await runner.wait()
    saved = await repository.get(saved.id)
    assert saved.status == "done"
    assert saved.attempt == 2
    assert saved.report_revision == 1


async def test_shutdown_marks_live_job_interrupted(repository, new_job, tmp_path):
    pipeline = ControlledPipeline()
    runner = Runner(repository, Settings(_env_file=None, data_dir=tmp_path), pipeline)
    await repository.create(new_job)
    runner.start(new_job)
    await pipeline.entered.wait()
    await runner.close()
    saved = await repository.get(new_job.id)
    assert saved.status == "interrupted"
    assert saved.error.retryable


async def test_inference_runs_outside_database_transactions(repository, new_job, tmp_path):
    pipeline = ControlledPipeline()
    runner = Runner(repository, Settings(_env_file=None, data_dir=tmp_path), pipeline)
    await repository.create(new_job)
    runner.start(new_job)
    await pipeline.entered.wait()
    async with repository.pool.connection() as conn:
        row = await (
            await conn.execute(
                "SELECT count(*) AS n FROM pg_stat_activity WHERE datname=current_database() AND state='idle in transaction' AND pid<>pg_backend_pid()"
            )
        ).fetchone()
        assert row["n"] == 0
    pipeline.release.set()
    await runner.wait()


async def test_retry_records_the_current_llm_while_retaining_transcript_provenance(
    new_job, tmp_path
):
    from unittest.mock import AsyncMock

    from backend.schemas import DraftReport
    from backend.worker import Pipeline

    new_job.segments = [Segment(id="S1", start=0, end=1, text="Discussion only.")]
    new_job.provenance.llm = "old-model"
    new_job.provenance.llm_digest = "old-digest"
    asr = new_job.provenance.asr_model
    pipeline = Pipeline(Settings(_env_file=None))
    pipeline.ollama.tags = AsyncMock(
        return_value=[{"name": "qwen3.5:4b", "digest": "current-digest"}]
    )
    pipeline.ollama.extract = AsyncMock(
        return_value=DraftReport(
            title="Discussion",
            summary=[],
            topics=[],
            decisions=[],
            open_questions=[],
            risks=[],
            action_items=[],
        )
    )
    await pipeline.run(new_job, tmp_path, AsyncMock())
    assert new_job.provenance.llm == "qwen3.5:4b"
    assert new_job.provenance.llm_digest == "current-digest"
    assert new_job.provenance.asr_model == asr
