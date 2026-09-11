import json

import httpx
import pytest

from backend.config import Settings
from backend.pipeline.structure import ExtractionError, Ollama
from backend.schemas import Segment

EMPTY = {
    "title": "Discussion",
    "summary": [],
    "topics": [],
    "decisions": [],
    "open_questions": [],
    "risks": [],
    "action_items": [],
}


async def test_extraction_uses_local_schema_and_nonstreaming_without_thinking(respx_mock):
    route = respx_mock.post("http://127.0.0.1:11434/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={"done": True, "done_reason": "stop", "message": {"content": json.dumps(EMPTY)}},
        )
    )
    client = Ollama(Settings(_env_file=None))
    result = await client.extract(
        [Segment(id="S1", start=0, end=1, text="There are no tasks today.")], "en"
    )
    assert result.action_items == []
    payload = json.loads(route.calls[0].request.content)
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["format"]["type"] == "object"
    assert payload["keep_alive"] == 0
    assert "S1" in payload["messages"][1]["content"]


async def test_decoder_schema_avoids_large_repetitions_but_validation_keeps_bounds(respx_mock):
    # Ollama's grammar compiler rejects large nested bounded string repetitions.
    route = respx_mock.post("http://127.0.0.1:11434/api/chat").mock(
        return_value=httpx.Response(
            200, json={"done": True, "message": {"content": json.dumps(EMPTY)}}
        )
    )
    await Ollama(Settings(_env_file=None)).extract(
        [Segment(id="S1", start=0, end=1, text="Hi")], "en"
    )
    decoder = json.loads(route.calls[0].request.content)["format"]
    assert "maxLength" not in json.dumps(decoder)
    assert decoder["$defs"]["DraftAction"]["properties"]["priority"]["enum"]
    from pydantic import ValidationError

    from backend.schemas import DraftReport

    with pytest.raises(ValidationError):
        DraftReport.model_validate({**EMPTY, "title": "x" * 201})


async def test_truncation_is_retried_once_then_fails(respx_mock):
    route = respx_mock.post("http://127.0.0.1:11434/api/chat").mock(
        return_value=httpx.Response(
            200, json={"done": True, "done_reason": "length", "message": {"content": "{}"}}
        )
    )
    with pytest.raises(ExtractionError, match="complete|valid"):
        await Ollama(Settings(_env_file=None)).extract(
            [Segment(id="S1", start=0, end=1, text="Hi")], "en"
        )
    assert route.call_count == 2


async def test_invalid_json_can_recover_with_one_repair(respx_mock):
    route = respx_mock.post("http://127.0.0.1:11434/api/chat").mock(
        side_effect=[
            httpx.Response(200, json={"done": True, "message": {"content": "not json"}}),
            httpx.Response(200, json={"done": True, "message": {"content": json.dumps(EMPTY)}}),
        ]
    )
    result = await Ollama(Settings(_env_file=None)).extract(
        [Segment(id="S1", start=0, end=1, text="Hi")], "en"
    )
    assert result.title == "Discussion"
    assert route.call_count == 2


async def test_http_redirects_never_send_transcripts_to_external_service(respx_mock):
    respx_mock.post("http://127.0.0.1:11434/api/chat").mock(
        return_value=httpx.Response(307, headers={"location": "https://example.com/collect"})
    )
    external = respx_mock.post("https://example.com/collect")
    with pytest.raises(ExtractionError):
        await Ollama(Settings(_env_file=None)).extract(
            [Segment(id="S1", start=0, end=1, text="Private meeting")], "en"
        )
    assert not external.called


async def test_oversized_input_fails_before_any_request(respx_mock):
    with pytest.raises(ExtractionError, match="context|long"):
        await Ollama(Settings(_env_file=None)).extract(
            [Segment(id="S1", start=0, end=1000, text="x" * 100000)], "en"
        )
    assert not respx_mock.calls


def test_action_evidence_requires_known_field_names():
    from pydantic import ValidationError

    from backend.schemas import DraftAction

    with pytest.raises(ValidationError):
        DraftAction.model_validate(
            {
                "task": "Review",
                "assignee": "Alex",
                "speaker_id": None,
                "due_raw": "tomorrow",
                "priority": "unspecified",
                "conditions": [],
                "evidence": {"task": [], "assignee": [], "due_raw": [], "priority": []},
            }
        )


async def test_russian_transcript_of_a_realistic_meeting_fits_the_context(respx_mock):
    """Byte-counting rejected Russian meetings at roughly a quarter of the usable context."""
    route = respx_mock.post("http://127.0.0.1:11434/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={"done": True, "done_reason": "stop", "message": {"content": json.dumps(EMPTY)}},
        )
    )
    line = "Мы обсудили бюджет проекта и решили перенести срок поставки оборудования"
    segments = [
        Segment(id=f"S{i}", start=i * 5.0, end=i * 5.0 + 5, text=line) for i in range(1, 101)
    ]
    await Ollama(Settings(_env_file=None)).extract(segments, "ru")
    assert route.called


def test_capacity_is_checked_before_the_speaker_stage_runs():
    """An over-long transcript must fail in seconds, not after diarization."""
    client = Ollama(Settings(_env_file=None))
    line = "Мы обсудили бюджет проекта и решили перенести срок поставки оборудования"
    short = [Segment(id=f"S{i}", start=i * 5.0, end=i * 5.0 + 5, text=line) for i in range(1, 51)]
    long = [Segment(id=f"S{i}", start=i * 5.0, end=i * 5.0 + 5, text=line) for i in range(1, 601)]

    client.check_capacity(short, "ru")
    with pytest.raises(ExtractionError, match="prompt tokens"):
        client.check_capacity(long, "ru")
