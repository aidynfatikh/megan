"""Readiness probes never download artifacts or load a model."""

import importlib.util
import platform
import shutil
import sys

import psycopg

from backend.config import Settings
from backend.pipeline.structure import Ollama


def asr_available(settings: Settings) -> bool:
    model = settings.asr_model_path
    if settings.asr_backend == "whisper_cpp":
        return (
            model.is_file()
            and model.stat().st_size > 0
            and bool(shutil.which(settings.whisper_cpp_bin))
        )
    return bool(importlib.util.find_spec("faster_whisper")) and all(
        (model / name).is_file() and (model / name).stat().st_size > 0
        for name in ("model.bin", "config.json", "tokenizer.json", "preprocessor_config.json")
    )


async def preflight(settings: Settings):
    checks = {
        "ffmpeg": bool(shutil.which("ffmpeg") and shutil.which("ffprobe")),
        "asr": asr_available(settings),
        "frontend": (settings.frontend_dir / "index.html").is_file(),
        "postgresql": False,
        "ollama": False,
    }
    details = {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "asr_backend": settings.asr_backend,
        "asr_model": str(settings.asr_model_path),
        "llm": settings.ollama_model,
        "context": settings.llm_context,
        "note": "Readiness checks do not establish GPU compatibility, output accuracy, or offline operation.",
    }
    try:
        async with await psycopg.AsyncConnection.connect(
            settings.database_url, connect_timeout=3
        ) as conn:
            version = await (await conn.execute("SHOW server_version")).fetchone()
            details["postgresql_version"] = version[0]
            checks["postgresql"] = True
    except psycopg.Error:
        details["database_error"] = (
            "Cannot connect to local PostgreSQL. Check DATABASE_URL and database startup."
        )
    try:
        selected = next(
            (m for m in await Ollama(settings).tags() if m.get("name") == settings.ollama_model),
            None,
        )
        checks["ollama"] = selected is not None
        details["llm_digest"] = selected.get("digest") if selected else None
    except Exception:
        details["ollama_error"] = (
            "Start the project Ollama server and download the configured model during setup."
        )
    return {"ready": all(checks.values()), "checks": checks, "details": details}
