import asyncio
import io
import wave

import httpx
import pytest

from backend.config import Settings
from backend.main import create_app
from backend.pipeline.validate import ground_report
from backend.schemas import DraftReport, Segment

pytestmark = pytest.mark.integration


async def test_chat_passes_current_speaker_names_and_scope(api, repository, new_job, monkeypatch):
    from unittest.mock import AsyncMock

    from backend.schemas import ChatAnswer, Report, Speaker

    new_job.status = "done"
    new_job.report = Report(title="Voice review")
    new_job.speakers = [Speaker(id="speaker_0", name="Дана", name_source="user_edit")]
    new_job.segments = [
        Segment(id="S1", start=0, end=1, speaker_id="speaker_0", text="Бюджет не утверждён.")
    ]
    await repository.create(new_job)
    await repository.save(new_job, new_revision=True)
    answer = AsyncMock(
        return_value=ChatAnswer(answer="Не утверждён", citations=[], supported=False)
    )
    monkeypatch.setattr("backend.main.answer_question", answer)
    client, _ = api
    response = await client.post(
        f"/api/jobs/{new_job.id}/chat",
        json={"question": "Что с бюджетом?", "speaker_id": "speaker_0"},
    )
    assert response.status_code == 200
    assert answer.call_args.args[3] == new_job.speakers
    assert answer.call_args.args[4] == "speaker_0"
    response = await client.post(
        f"/api/jobs/{new_job.id}/chat",
        json={"question": "Что с бюджетом?", "speaker_id": "unknown"},
    )
    assert response.status_code == 422


async def test_notion_export_rejects_a_stale_displayed_revision(api, repository, new_job):
    from backend.schemas import Report

    new_job.status = "done"
    new_job.report = Report(title="Current report")
    await repository.create(new_job)
    await repository.save(new_job, new_revision=True)
    client, _ = api
    response = await client.post(f"/api/jobs/{new_job.id}/notion", json={"revision": 2})
    assert response.status_code == 409


class TestPipeline:
    __test__ = False

    async def run(self, job, directory, checkpoint):
        job.segments = [
            Segment(id="S1", start=0, end=1, text="Dana will send the estimate tomorrow.")
        ]
        job.duration_sec = 1
        await checkpoint("analyze")
        await asyncio.sleep(0.03)
        quote = {"segment_id": "S1", "quote": job.segments[0].text}
        data = {
            "title": "Budget review",
            "summary": [],
            "topics": [],
            "decisions": [],
            "open_questions": [],
            "risks": [],
            "action_items": [
                {
                    "task": "Send the estimate",
                    "assignee": "Dana",
                    "speaker_id": None,
                    "due_raw": "tomorrow",
                    "priority": "unspecified",
                    "conditions": [],
                    "evidence": {
                        "task": [quote],
                        "assignee": [quote],
                        "due": [quote],
                        "priority": [],
                    },
                }
            ],
        }
        return ground_report(DraftReport.model_validate(data), job.segments, job.meeting_date)


@pytest.fixture
async def api(repository, tmp_path):
    app = create_app(
        Settings(_env_file=None, data_dir=tmp_path), repository=repository, pipeline=TestPipeline()
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            yield client, app


def audio():
    stream = io.BytesIO()
    with wave.open(stream, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x01\x00" * 16000)
    return stream.getvalue()


async def upload_and_wait(client, app):
    response = await client.post(
        "/api/jobs",
        files={"file": ("meeting.wav", audio(), "audio/wav")},
        data={"meeting_date": "2026-09-11", "report_language": "en"},
    )
    assert response.status_code == 202, response.text
    job_id = response.json()["id"]
    await app.state.runner.wait()
    return job_id


async def test_upload_process_export_and_persistent_history(api):
    client, app = api
    job_id = await upload_and_wait(client, app)
    result = (await client.get(f"/api/jobs/{job_id}")).json()
    assert result["status"] == "done"
    assert result["report"]["action_items"][0]["due"]["date"] == "2026-09-12"
    exported = await client.get(f"/api/jobs/{job_id}/export?format=json")
    assert exported.status_code == 200
    assert exported.json() == result
    assert "attachment" in exported.headers["content-disposition"]
    assert (await client.get("/api/jobs")).json()[0]["id"] == job_id


async def test_audio_supports_byte_ranges_for_evidence_playback(api):
    client, app = api
    job_id = await upload_and_wait(client, app)
    response = await client.get(f"/api/jobs/{job_id}/audio", headers={"Range": "bytes=0-43"})
    assert response.status_code == 206
    assert response.content == audio()[:44]
    assert response.headers["content-range"].startswith("bytes 0-43/")


async def test_edit_increments_revision_clears_checks_and_rejects_stale_writes(api):
    client, app = api
    job_id = await upload_and_wait(client, app)
    change = {
        "revision": 1,
        "task": "Send a revised estimate",
        "assignee": "Dana",
        "due_date": "2026-09-15",
        "priority": "high",
    }
    response = await client.patch(f"/api/jobs/{job_id}/action-items/A1", json=change)
    assert response.status_code == 200
    updated = response.json()
    assert updated["report_revision"] == 2
    item = updated["report"]["action_items"][0]
    assert item["review"]["state"] == "edited"
    assert item["checks"]["quotes_match"] is False
    assert item["due"]["resolution"] == "user_edit"
    assert (
        await client.patch(f"/api/jobs/{job_id}/action-items/A1", json=change)
    ).status_code == 409
    exported = (await client.get(f"/api/jobs/{job_id}/export?format=json")).json()
    assert exported["report"]["action_items"][0]["task"] == change["task"]


async def test_bad_input_never_creates_a_permanently_active_job(api):
    client, app = api
    response = await client.post(
        "/api/jobs", files={"file": ("../../evil.exe", b"x", "application/octet-stream")}
    )
    assert response.status_code == 415
    assert (await client.get("/api/jobs")).json() == []
    assert not app.state.runner.busy
    response = await client.post("/api/jobs", files={"file": ("meeting.wav", b"", "audio/wav")})
    assert response.status_code == 400
    assert not app.state.runner.busy


async def test_path_traversal_and_unknown_export_are_rejected(api):
    client, app = api
    assert (await client.get("/api/jobs/not-a-uuid/audio")).status_code == 422
    job_id = await upload_and_wait(client, app)
    assert (await client.get(f"/api/jobs/{job_id}/export?format=exe")).status_code == 422


async def test_examples_are_explicitly_labeled_and_do_not_use_real_uploads(api):
    client, app = api
    result = await client.get("/api/example")
    assert result.status_code == 200
    assert result.json()["provenance"]["sample"] is True
    assert (await client.get("/api/jobs")).json() == []


async def test_speaker_rename_persists_exports_and_preserves_named_nonparticipants(api, repository):
    from uuid import UUID

    from backend.schemas import Speaker

    client, app = api
    job_id = await upload_and_wait(client, app)
    job = await repository.get(UUID(job_id))
    job.speakers = [Speaker(id="speaker_0", name="Speaker 1")]
    job.segments[0].speaker_id = "speaker_0"
    job.diarization_status = "done"
    named = job.report.action_items[0]
    anonymous = named.model_copy(
        deep=True, update={"id": "A2", "assignee": None, "speaker_id": "speaker_0"}
    )
    job.report.action_items.append(anonymous)
    await repository.save(job)
    path = f"/api/jobs/{job_id}/speakers/speaker_0"
    response = await client.patch(path, json={"revision": 1, "name": "Mira"})
    assert response.status_code == 200
    result = response.json()
    assert result["report_revision"] == 2
    assert result["speakers"][0]["name_source"] == "user_edit"
    assert result["segments"][0]["speaker_id"] == "speaker_0"
    assert result["report"]["action_items"][0]["assignee"] == "Dana"
    assert result["report"]["action_items"][1]["assignee"] == "Mira"
    saved = await repository.get(UUID(job_id))
    assert saved.diarization_status == "done"
    assert saved.speakers[0].name == "Mira"
    assert (await client.patch(path, json={"revision": 1, "name": "Stale"})).status_code == 409
    exported = await client.get(f"/api/jobs/{job_id}/export?format=csv")
    assert "Mira" in exported.text and "Dana" in exported.text
