"""Readiness probes never download artifacts or load a model."""

import importlib.util
import platform
import shutil
import sys

import psycopg

from backend.config import Settings
from backend.pipeline.asr import offline_env
from backend.pipeline.process import run_process
from backend.pipeline.structure import Ollama


def tokenizer_available(settings: Settings) -> bool:
    """The report tokenizer bounds prompt length for the models it covers.

    Without it, prompt_tokens falls back to counting UTF-8 bytes, which is deliberately strict
    and rejects Russian and Kazakh meetings at roughly a quarter of the tested capacity. Setup
    downloads and checksums the file, so a machine missing it is not in the tested profile.
    """
    if not settings.ollama_model.startswith("qwen3.5:"):
        return True
    path = settings.llm_tokenizer_path
    return path.is_file() and path.stat().st_size > 0


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
        "report_tokenizer": tokenizer_available(settings),
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
    if not checks["report_tokenizer"]:
        details["report_tokenizer_warning"] = (
            "The pinned report tokenizer is missing, so prompt length falls back to a strict "
            "byte count and long Russian or Kazakh meetings will be refused early. Run model setup."
        )
    details["diarization_backend"] = settings.diarization_backend
    details["diarization_ready"] = await diarization_available(settings)
    if not details["diarization_ready"]:
        details["diarization_warning"] = (
            "Optional speaker separation is unavailable. Core reports can still run. "
            "Check the local checkpoint, format, device, and runtime path."
        )
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


async def diarization_available(settings: Settings) -> bool:
    if settings.diarization_backend == "none":
        return True
    model = settings.diarization_model_path
    nemo = settings.diarization_backend == "sortformer_nemo"
    if (
        not model.is_file()
        or not model.stat().st_size
        or model.suffix != (".nemo" if nemo else ".gguf")
    ):
        return False
    if not nemo:
        return bool(shutil.which(settings.nemo_speech_bin))
    if settings.diarization_device == "metal":
        return False
    try:
        await run_process(
            settings.diarization_python,
            "-c",
            "import importlib.util, sys; sys.exit(0 if all(importlib.util.find_spec(n) is not None for n in ('nemo', 'torch')) else 1)",
            timeout=5,
            env=offline_env(),
        )
        return True
    except Exception:
        return False
