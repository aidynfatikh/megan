import asyncio
import logging
import time
from pathlib import Path
from uuid import UUID

from backend.config import Settings
from backend.db import BusyError, Repository
from backend.pipeline.asr import transcribe
from backend.pipeline.audio import AudioError, normalize_audio
from backend.pipeline.structure import ExtractionError, Ollama
from backend.pipeline.validate import ground_report
from backend.schemas import Job, JobError, Report

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.ollama = Ollama(settings)

    async def run(self, job: Job, directory: Path, checkpoint):
        wav = directory / "normalized.wav"
        if not job.segments:
            await checkpoint("decode")
            source = directory / f"original{Path(job.filename).suffix.lower()}"
            audio = await normalize_audio(
                source,
                wav,
                max_duration=self.settings.max_duration_sec,
                timeout=self.settings.stage_timeout_sec,
            )
            job.duration_sec = audio.duration
            if audio.silent:
                return Report(title="No usable speech", content_status="no_usable_speech")
            await checkpoint("release_models")
            await self.ollama.unload()
            await checkpoint("transcribe")
            job.provenance.asr_backend = self.settings.asr_backend
            job.provenance.asr_model = self.settings.asr_model_path.name
            job.segments = await transcribe(self.settings, wav, directory / "transcript.json")
            if any(s.end > audio.duration + 1 for s in job.segments):
                raise AudioError("ASR timestamps extend beyond the recording.")
            # A small terminal timestamp overrun can arise from ASR frame rounding.
            for segment in job.segments:
                segment.end = min(segment.end, audio.duration)
                segment.start = min(segment.start, segment.end)
            await checkpoint("transcript_ready")
        if not job.segments:
            return Report(title="No usable speech", content_status="no_usable_speech")
        await checkpoint("analyze")
        job.provenance.llm = self.settings.ollama_model
        selected = next(
            (m for m in await self.ollama.tags() if m.get("name") == self.settings.ollama_model),
            None,
        )
        job.provenance.llm_digest = selected.get("digest") if selected else None
        draft = await self.ollama.extract(job.segments, job.report_language)
        await checkpoint("check_sources")
        report = ground_report(draft, job.segments, job.meeting_date)
        for key, value in self.ollama.last_metrics.items():
            if key.endswith("duration"):
                job.timings[f"llm_{key}"] = value / 1e9
        return report


class Runner:
    def __init__(self, repository: Repository, settings: Settings, pipeline=None):
        self.repo = repository
        self.settings = settings
        self.pipeline = pipeline or Pipeline(settings)
        self.task: asyncio.Task | None = None
        self.reserved = False

    @property
    def busy(self):
        return self.reserved or (self.task is not None and not self.task.done())

    def reserve(self):
        if self.busy:
            raise BusyError("A meeting or question is already processing. Please wait.")
        self.reserved = True

    def release(self):
        self.reserved = False

    def start(self, job: Job):
        if self.task is not None and not self.task.done():
            raise BusyError("A meeting is already processing")
        self.reserved = True
        self.task = asyncio.create_task(self._run(job), name=f"meeting-{job.id}")

    async def _run(self, job: Job):
        started = last = time.monotonic()
        previous_stage = None
        job.status = "running"
        job.error = None

        async def checkpoint(stage):
            nonlocal last, previous_stage
            now = time.monotonic()
            if previous_stage:
                job.timings[previous_stage] = now - last
            job.stage = stage
            job.elapsed_sec = now - started
            await self.repo.save(job)
            last, previous_stage = now, stage

        try:
            directory = self.settings.data_dir.resolve() / "jobs" / str(job.id)
            job.report = await self.pipeline.run(job, directory, checkpoint)
            await checkpoint("persist")
            job.status = "done"
            job.stage = "done"
            job.elapsed_sec = time.monotonic() - started
            await self.repo.save(job, new_revision=True)
        except asyncio.CancelledError:
            job.status = "interrupted"
            job.error = JobError(
                code="interrupted",
                stage=job.stage,
                message="Processing stopped. Retry to continue from the saved transcript.",
            )
            job.elapsed_sec = time.monotonic() - started
            await self.repo.save(job)
        except Exception as exc:
            logger.exception("Meeting %s failed during %s", job.id, job.stage)
            job.status = "failed"
            safe_message = (
                str(exc)
                if isinstance(exc, (AudioError, ExtractionError))
                else "Processing failed. Check local runtime logs and retry."
            )
            job.error = JobError(code="pipeline_error", stage=job.stage, message=safe_message)
            job.elapsed_sec = time.monotonic() - started
            await self.repo.save(job)
        finally:
            self.release()

    async def retry(self, job_id: UUID):
        self.reserve()
        try:
            job = await self.repo.get(job_id)
            if job is None:
                raise KeyError(job_id)
            if job.status not in ("failed", "interrupted"):
                raise ValueError("Only failed or interrupted meetings can be retried")
            job.status = "queued"
            job.stage = "queued"
            job.error = None
            job.attempt += 1
            job.timings = {}
            job.elapsed_sec = 0
            await self.repo.save(job)
            self.start(job)
            return job
        except BaseException:
            self.release()
            raise

    async def wait(self):
        if self.task:
            await self.task

    async def close(self):
        if self.task and not self.task.done():
            self.task.cancel()
            await self.task
