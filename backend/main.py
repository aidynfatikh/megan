import asyncio
import json
import logging
import shutil
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.config import Settings
from backend.db import BusyError, ConflictError, Repository
from backend.demo import seed_demo
from backend.example import example_job
from backend.notion import (
    NotionConnect,
    NotionError,
    NotionExporter,
    NotionExportRequest,
    NotionResult,
)
from backend.pipeline.export import export_csv, export_ics
from backend.pipeline.rag import answer_question
from backend.pipeline.structure import ExtractionError, Ollama
from backend.runtime import asr_available, diarization_available
from backend.schemas import ActionPatch, ChatRequest, Due, Job, Provenance, SpeakerPatch
from backend.worker import Runner

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, *, repository=None, pipeline=None):
    settings = settings or Settings()
    repo = repository or Repository(settings.database_url)
    notion = NotionExporter(settings, repo)

    @asynccontextmanager
    async def lifespan(app):
        app.state.database_ready = False
        app.state.runner = Runner(repo, settings, pipeline)
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        try:
            if repository is None:
                await repo.open()
                await repo.migrate()
                await repo.acquire_runner()
                await repo.recover()
                if settings.demo_seed_dir:
                    await seed_demo(repo, settings.demo_seed_dir, settings.data_dir)
            app.state.database_ready = True
        except Exception:
            logger.exception(
                "PostgreSQL startup failed. Check DATABASE_URL and run migrations/preflight."
            )
        try:
            yield
        finally:
            await app.state.runner.close()
            if repository is None:
                await repo.close()

    app = FastAPI(title="Megan", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(BusyError)
    async def busy_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(ConflictError)
    async def conflict_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(ExtractionError)
    async def extraction_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=503)

    @app.exception_handler(NotionError)
    async def notion_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=502)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        if request.url.path == "/api/integrations/notion":
            # Validation errors normally echo the input. Never reflect a credential.
            return JSONResponse(
                {"detail": "Enter a valid token and UUIDs for optional Notion IDs."},
                status_code=422,
            )
        return await request_validation_exception_handler(request, exc)

    @app.middleware("http")
    async def request_limits(request, call_next):
        length = request.headers.get("content-length")
        if length:
            try:
                if int(length) > settings.max_upload_mb * 1024 * 1024 + 1024 * 1024:
                    return JSONResponse(
                        {"detail": "Upload exceeds the configured size limit."}, status_code=413
                    )
            except ValueError:
                return JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)
        return await call_next(request)

    def require_database():
        if not app.state.database_ready:
            raise HTTPException(
                503, "PostgreSQL is unavailable. Start the local database, then restart Megan."
            )

    async def get_job(job_id: UUID):
        require_database()
        job = await repo.get(job_id)
        if job is None:
            raise HTTPException(404, "Meeting not found")
        return job

    @app.get("/api/health")
    async def health():
        database = app.state.database_ready
        if database:
            try:
                await repo.healthy()
            except Exception:
                database = False
        asr = asr_available(settings)
        ollama, digest = False, None
        try:
            models = await Ollama(settings).tags()
            selected = next((m for m in models if m.get("name") == settings.ollama_model), None)
            ollama = selected is not None
            digest = selected.get("digest") if selected else None
        except Exception:
            pass
        ffmpeg = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
        return {
            "ready": database and asr and ollama and ffmpeg,
            "database": database,
            "asr": asr,
            "ollama": ollama,
            "ffmpeg": ffmpeg,
            "busy": app.state.runner.busy,
            "local_only": True,
            "asr_backend": settings.asr_backend,
            "asr_model": settings.asr_model_path.name,
            "llm": settings.ollama_model,
            "llm_digest": digest,
            "diarization": settings.diarization_backend,
            "diarization_ready": await diarization_available(settings),
            "chat_enabled": settings.enable_chat,
            "max_upload_mb": settings.max_upload_mb,
            "max_duration_sec": settings.max_duration_sec,
        }

    @app.get("/api/example", response_model=Job)
    async def example():
        return example_job()

    @app.get("/api/integrations/notion")
    async def notion_status():
        return notion.status()

    @app.post("/api/integrations/notion")
    async def notion_connect(request: NotionConnect):
        return await notion.connect(request)

    @app.post("/api/jobs/{job_id}/notion", response_model=NotionResult)
    async def notion_export(job_id: UUID, request: NotionExportRequest):
        job = await get_job(job_id)
        if job.report_revision != request.revision:
            raise ConflictError("This report changed. Reload before exporting.")
        return await notion.export(job)

    @app.get("/api/jobs", response_model=list[Job])
    async def list_jobs():
        require_database()
        return await repo.list()

    @app.post("/api/jobs", status_code=202, response_model=Job)
    async def upload(
        file: Annotated[UploadFile, File()],
        meeting_date: Annotated[date | None, Form()] = None,
        report_language: Annotated[Literal["ru", "kk", "en"], Form()] = "ru",
        spoken_language: Annotated[Literal["auto", "ru", "kk", "en"] | None, Form()] = None,
    ):
        require_database()
        name = Path((file.filename or "").replace("\\", "/")).name
        suffix = Path(name).suffix.lower()
        if suffix not in {".mp3", ".wav", ".m4a"}:
            raise HTTPException(415, "Use an MP3, WAV, or M4A file")
        if pipeline is None:
            readiness = await health()
            if not readiness["ready"]:
                raise HTTPException(
                    503,
                    "Local models or audio tools are not ready. Open system status and run setup.",
                )
        runner = app.state.runner
        runner.reserve()
        directory = None
        try:
            job_id = uuid4()
            directory = settings.data_dir.resolve() / "jobs" / str(job_id)
            directory.mkdir(parents=True)
            total = 0
            with (directory / f"original{suffix}").open("wb") as stream:
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > settings.max_upload_mb * 1024 * 1024:
                        raise HTTPException(413, "The recording exceeds the upload size limit")
                    stream.write(chunk)
            if not total:
                raise HTTPException(400, "The recording is empty")
            now = datetime.now(UTC)
            job = Job(
                id=job_id,
                filename=name[:255],
                created_at=now,
                updated_at=now,
                meeting_date=meeting_date,
                report_language=report_language,
                spoken_language=spoken_language,
                diarization_status="pending"
                if settings.diarization_backend != "none"
                else "disabled",
                provenance=Provenance(
                    asr_backend=settings.asr_backend,
                    asr_model=settings.asr_model_path.name,
                    llm=settings.ollama_model,
                    llm_digest=readiness.get("llm_digest") if pipeline is None else None,
                ),
            )
            await repo.create(job)
            runner.start(job)
            return job
        except BaseException:
            runner.release()
            if directory:
                shutil.rmtree(directory, ignore_errors=True)
            raise
        finally:
            await file.close()

    @app.get("/api/jobs/{job_id}", response_model=Job)
    async def job_detail(job_id: UUID):
        return await get_job(job_id)

    @app.post("/api/jobs/{job_id}/retry", status_code=202, response_model=Job)
    async def retry(job_id: UUID):
        await get_job(job_id)
        try:
            return await app.state.runner.retry(job_id)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/jobs/{job_id}/events")
    async def events(job_id: UUID):
        await get_job(job_id)

        async def stream():
            previous = None
            while True:
                job = await repo.get(job_id)
                payload = {"status": job.status, "stage": job.stage, "elapsed_sec": job.elapsed_sec}
                if payload != previous:
                    yield f"data: {json.dumps(payload)}\n\n"
                    previous = payload
                if job.status in ("done", "failed", "interrupted"):
                    return
                await asyncio.sleep(0.5)

        return StreamingResponse(
            stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )

    @app.get("/api/jobs/{job_id}/audio")
    async def audio(job_id: UUID):
        job = await get_job(job_id)
        root = settings.data_dir.resolve() / "jobs" / str(job_id)
        normalized = root / "normalized.wav"
        path = (
            normalized
            if normalized.exists()
            else root / f"original{Path(job.filename).suffix.lower()}"
        )
        if not path.exists() or not path.resolve().is_relative_to(root):
            raise HTTPException(404, "Recording not found")
        return FileResponse(
            path,
            media_type="audio/wav"
            if path.suffix == ".wav"
            else "audio/mpeg"
            if path.suffix == ".mp3"
            else "audio/mp4",
        )

    @app.get("/api/jobs/{job_id}/export")
    async def export(job_id: UUID, format: Literal["json", "csv", "ics"] = "json"):
        job = await get_job(job_id)
        if job.report is None:
            raise HTTPException(409, "The report is not ready")
        headers = {"Content-Disposition": f'attachment; filename="megan-{job_id}.{format}"'}
        if format == "json":
            return Response(
                job.model_dump_json(indent=2), media_type="application/json", headers=headers
            )
        if format == "csv":
            return Response(
                export_csv(job.report, job.speakers),
                media_type="text/csv; charset=utf-8",
                headers=headers,
            )
        content, skipped = export_ics(job.report, str(job_id), job.speakers)
        headers["X-Skipped-Undated-Tasks"] = str(skipped)
        return Response(content, media_type="text/calendar; charset=utf-8", headers=headers)

    @app.patch("/api/jobs/{job_id}/action-items/{item_id}", response_model=Job)
    async def edit_action(job_id: UUID, item_id: str, patch: ActionPatch):
        job = await get_job(job_id)
        if job.status != "done" or not job.report:
            raise HTTPException(409, "Wait for the completed report before editing")
        item = next((a for a in job.report.action_items if a.id == item_id), None)
        if item is None:
            raise HTTPException(404, "Task not found")
        changed = [
            field
            for field in ("task", "assignee", "priority")
            if getattr(item, field) != getattr(patch, field)
        ]
        if item.due.date != patch.due_date:
            changed.append("due")
        if changed:
            for field in ("task", "assignee", "priority"):
                setattr(item, field, getattr(patch, field))
            if "assignee" in changed:
                item.speaker_id = None
            if "due" in changed:
                item.due = Due(raw=item.due.raw, date=patch.due_date, resolution="user_edit")
            item.edited_fields = sorted(set(item.edited_fields + changed))
            item.checks.quotes_match = False
            item.review.state = "edited"
            item.review.reasons = sorted(
                set(item.review.reasons + [f"user_edited:{f}" for f in changed])
            )
            await repo.save(job, new_revision=True, expected_revision=patch.revision)
        elif patch.revision != job.report_revision:
            raise ConflictError("This report changed. Reload before saving.")
        return job

    @app.patch("/api/jobs/{job_id}/speakers/{speaker_id}", response_model=Job)
    async def rename_speaker(job_id: UUID, speaker_id: str, patch: SpeakerPatch):
        job = await get_job(job_id)
        if job.status != "done":
            raise HTTPException(409, "Wait until processing is complete")
        speaker = next((s for s in job.speakers if s.id == speaker_id), None)
        if speaker is None:
            raise HTTPException(404, "Speaker not found")
        speaker.name = patch.name.strip()
        speaker.name_source = "user_edit"
        if not speaker.name:
            raise HTTPException(422, "A speaker name cannot be blank")
        if job.report:
            for action in job.report.action_items:
                if action.speaker_id == speaker_id:
                    action.assignee = speaker.name
                    action.edited_fields = sorted(set(action.edited_fields + ["assignee"]))
                    action.review.state = "edited"
                    action.checks.quotes_match = False
        await repo.save(job, new_revision=True, expected_revision=patch.revision)
        return job

    @app.post("/api/jobs/{job_id}/chat")
    async def chat(job_id: UUID, request: ChatRequest):
        if not settings.enable_chat:
            raise HTTPException(404, "Meeting chat is disabled")
        job = await get_job(job_id)
        if job.status != "done":
            raise HTTPException(409, "Wait until the report is ready")
        if request.speaker_id is not None and request.speaker_id not in {
            s.id for s in job.speakers
        }:
            raise HTTPException(422, "Speaker not found in this meeting")
        app.state.runner.reserve()
        try:
            return await answer_question(
                Ollama(settings), request.question, job.segments, job.speakers, request.speaker_id
            )
        finally:
            app.state.runner.release()

    frontend = settings.frontend_dir.resolve()
    if (frontend / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    async def index():
        if (frontend / "index.html").is_file():
            return FileResponse(frontend / "index.html")
        return JSONResponse(
            {
                "message": "Megan API is running. Start the frontend or build it with npm run build.",
                "schema": "/openapi.json",
            }
        )

    return app


app = create_app()
