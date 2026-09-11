import json
from datetime import date

import pytest

from backend.cli import process_file
from backend.config import Settings
from backend.runtime import asr_available


async def test_cli_uploads_to_local_api_and_exports_completed_job(respx_mock, tmp_path):
    recording = tmp_path / "meeting.wav"
    recording.write_bytes(b"test recording")
    respx_mock.post("http://127.0.0.1:8000/api/jobs").respond(202, json={"id": "job1"})
    respx_mock.get("http://127.0.0.1:8000/api/jobs/job1").respond(
        200, json={"id": "job1", "status": "done", "stage": "done"}
    )
    output = tmp_path / "report.json"
    await process_file(recording, date(2026, 9, 11), "en", output, "http://127.0.0.1:8000")
    assert json.loads(output.read_text())["status"] == "done"
    upload = respx_mock.calls[0].request.content
    assert b"test recording" in upload
    assert b"2026-09-11" in upload


async def test_cli_rejects_remote_endpoint_before_reading_or_uploading(respx_mock, tmp_path):
    with pytest.raises(ValueError, match="loopback"):
        await process_file(
            tmp_path / "private.wav", None, "ru", tmp_path / "out.json", "https://example.com"
        )
    assert not respx_mock.calls


async def test_cli_surfaces_processing_failure_and_keeps_job_id(respx_mock, tmp_path):
    recording = tmp_path / "meeting.wav"
    recording.write_bytes(b"test")
    respx_mock.post("http://127.0.0.1:8000/api/jobs").respond(202, json={"id": "job1"})
    respx_mock.get("http://127.0.0.1:8000/api/jobs/job1").respond(
        200,
        json={
            "id": "job1",
            "status": "failed",
            "stage": "analyze",
            "error": {"message": "LLM failed"},
        },
    )
    with pytest.raises(RuntimeError, match="job1.*LLM failed"):
        await process_file(recording, None, "ru", tmp_path / "out.json", "http://127.0.0.1:8000")


def test_asr_readiness_requires_complete_model_files(tmp_path, monkeypatch):
    settings = Settings(_env_file=None, asr_backend="faster_whisper", asr_model_path=tmp_path)
    monkeypatch.setattr("backend.runtime.importlib.util.find_spec", lambda name: object())
    assert not asr_available(settings)
    for filename in ("model.bin", "config.json", "tokenizer.json", "preprocessor_config.json"):
        (tmp_path / filename).write_bytes(b"x")
    assert asr_available(settings)
