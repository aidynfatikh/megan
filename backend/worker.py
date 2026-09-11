import asyncio
import json
import logging
import time
from pathlib import Path
from uuid import UUID

from backend.config import Settings
from backend.db import BusyError, Repository
from backend.pipeline.asr import transcribe
from backend.pipeline.audio import AudioError, normalize_audio
from backend.pipeline.chunking import plan_chunks
from backend.pipeline.diarize import align_speakers, diarize
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
        # Older failed jobs may have saved ASR output before timestamp validation.
        # Retry transcription instead of using those invalid sources in a report.
        if job.duration_sec is not None and any(
            segment.end > job.duration_sec + 1 for segment in job.segments
        ):
            job.segments = []
        if self.settings.diarization_backend == "none" and job.diarization_status != "done":
            job.diarization_status = "disabled"
            job.provenance.diarization_backend = "none"
            job.provenance.diarization_model = None
            job.provenance.diarization_model_sha256 = None
            job.provenance.diarization_runtime = None
            job.warnings = [w for w in job.warnings if not w.startswith("Speaker separation")]
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
                job.diarization_status = "disabled"
                return Report(title="No usable speech", content_status="no_usable_speech")
            await checkpoint("release_models")
            await self.ollama.unload()
            await checkpoint("transcribe")
            job.provenance.asr_backend = self.settings.asr_backend
            job.provenance.asr_model = self.settings.asr_model_path.name
            segments = await transcribe(self.settings, wav, directory / "transcript.json")
            if any(s.end > audio.duration + 1 for s in segments):
                raise AudioError("ASR timestamps extend beyond the recording.")
            # A small terminal timestamp overrun can arise from ASR frame rounding.
            for segment in segments:
                segment.end = min(segment.end, audio.duration)
                segment.start = min(segment.start, segment.end)
            job.segments = segments
            await checkpoint("transcript_ready")
        if not job.segments:
            job.diarization_status = "disabled"
            return Report(title="No usable speech", content_status="no_usable_speech")
        # A transcript larger than the prompt budget is split into consecutive parts rather than
        # refused. Planning it here also fails a genuinely impossible input before the speaker
        # stage runs. The bound inside the extraction client remains authoritative.
        chunks = plan_chunks(job.segments, self.settings, job.report_language)
        if len(chunks) > 1:
            job.warnings = [w for w in job.warnings if not w.startswith("This meeting was")]
            job.warnings.append(
                f"This meeting was longer than one prompt, so it was read in {len(chunks)} "
                "consecutive parts and merged. Later parts override earlier ones; review "
                "decisions and tasks that changed during the meeting."
            )
        else:
            self.ollama.check_capacity(job.segments, job.report_language)
        if self.settings.diarization_backend != "none" and job.diarization_status != "done":
            job.diarization_status = "running"
            job.provenance.diarization_backend = self.settings.diarization_backend
            job.provenance.diarization_model = self.settings.diarization_model_path.name
            job.provenance.diarization_model_sha256 = None
            job.provenance.diarization_runtime = None
            # Also unload before a transcript-only retry, which can follow a chat request.
            # Failure to unload is fatal: starting another GPU model would be unsafe.
            await checkpoint("release_models")
            await self.ollama.unload()
            await checkpoint("diarize")
            job.warnings = [w for w in job.warnings if not w.startswith("Speaker separation")]
            try:
                result = await diarize(self.settings, wav, directory, job.duration_sec or 0)
                job.segments, job.speakers = align_speakers(job.segments, result.turns)
                job.provenance.diarization_model_sha256 = result.model_sha256
                job.provenance.diarization_runtime = result.runtime
                job.diarization_status = "done"
                unknown = sum(s.speaker_id is None for s in job.segments)
                job.warnings.append(
                    "Speaker separation supports up to four voices; labels need review. "
                    f"{unknown} of {len(job.segments)} transcript segments have unknown attribution."
                )
            except Exception:
                logger.exception("Optional speaker separation failed for %s", job.id)
                job.diarization_status = "failed"
                job.speakers = []
                for segment in job.segments:
                    segment.speaker_id = None
                job.warnings.append(
                    "Speaker separation failed. The report continues with unknown speakers. "
                    "Check the local Sortformer setup and runtime logs."
                )
            await checkpoint("speakers_ready")
        await checkpoint("analyze")
        job.provenance.llm = self.settings.ollama_model
        selected = next(
            (m for m in await self.ollama.tags() if m.get("name") == self.settings.ollama_model),
            None,
        )
        job.provenance.llm_digest = selected.get("digest") if selected else None
        try:
            draft = (
                await self.ollama.extract_long(chunks, job.report_language)
                if len(chunks) > 1
                else await self.ollama.extract(job.segments, job.report_language)
            )
        finally:
            (directory / "extraction.attempts.json").write_text(
                json.dumps(self.ollama.last_attempts, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        (directory / "extraction.draft.json").write_text(
            draft.model_dump_json(indent=2), encoding="utf-8"
        )
        await checkpoint("check_sources")
        report = ground_report(draft, job.segments, job.meeting_date)
        job.warnings = [w for w in job.warnings if not w.startswith("Decision review:")]
        filtered = sum(d.status == "confirmed" for d in draft.decisions) - len(report.decisions)
        if filtered:
            job.warnings.append(
                f"Decision review: {filtered} suggested decisions lacked explicit agreement "
                "in their cited words. Check the transcript for implicit decisions."
            )
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
