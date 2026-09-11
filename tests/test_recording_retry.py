"""A report retry must never turn rejected recording timestamps into evidence."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.config import Settings
from backend.pipeline.audio import AudioError
from backend.schemas import Segment
from backend.worker import Pipeline


@pytest.mark.parametrize("saved_invalid_transcript", [False, True])
async def test_invalid_asr_is_not_reused_or_persisted_as_valid_sources(
    new_job, tmp_path, monkeypatch, saved_invalid_transcript
):
    new_job.duration_sec = 33
    invalid = Segment(id="S1", start=30, end=60, text="Unsupported terminal phrase.")
    if saved_invalid_transcript:
        new_job.segments = [invalid]
    normalize = AsyncMock(return_value=SimpleNamespace(duration=33, silent=False))
    transcribe = AsyncMock(return_value=[invalid])
    monkeypatch.setattr("backend.worker.normalize_audio", normalize)
    monkeypatch.setattr("backend.worker.transcribe", transcribe)
    pipeline = Pipeline(Settings(_env_file=None, diarization_backend="none"))
    pipeline.ollama.unload = AsyncMock()
    pipeline.ollama.extract = AsyncMock()

    with pytest.raises(AudioError, match="timestamps extend beyond"):
        await pipeline.run(new_job, tmp_path, AsyncMock())

    transcribe.assert_awaited_once()
    pipeline.ollama.extract.assert_not_awaited()
    assert new_job.segments == []
