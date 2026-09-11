"""Opt-in real-model regression cases; saved outputs still need human review."""

import json
import os
from datetime import date
from pathlib import Path

import pytest

from backend.config import Settings
from backend.pipeline.rag import answer_question
from backend.pipeline.structure import Ollama
from backend.pipeline.validate import ground_report
from backend.schemas import Segment

CASES = json.loads((Path(__file__).parent / "fixtures/extraction_cases.json").read_text())
pytestmark = [
    pytest.mark.models,
    pytest.mark.skipif(
        os.getenv("MEGAN_TEST_MODELS") != "1",
        reason="Set MEGAN_TEST_MODELS=1 for real local inference",
    ),
]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
async def test_extraction_preserves_annotated_commitments(case):
    segments = [
        Segment(id=f"S{i}", start=(i - 1) * 10, end=i * 10, text=text)
        for i, text in enumerate(case["text"], 1)
    ]
    model = Ollama(Settings())
    draft = await model.extract(segments, case["language"])
    report = ground_report(draft, segments, date(2026, 9, 11))
    directory = Path(os.getenv("MEGAN_MODEL_RESULTS", ".local/evaluation/model-cases"))
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{case['id']}-draft.json").write_text(
        draft.model_dump_json(indent=2), encoding="utf-8"
    )
    (directory / f"{case['id']}.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    assert [a.assignee for a in report.action_items] == case["owners"]
    assert [a.due.date.isoformat() if a.due.date else None for a in report.action_items] == case[
        "dates"
    ]
    assert all(a.priority == "unspecified" for a in report.action_items)
    assert all(a.checks.quotes_match and a.checks.references_valid for a in report.action_items)
    if case.get("conditional"):
        assert report.action_items[0].conditions
    if "decisions" in case:
        assert len(report.decisions) == case["decisions"]
    claims = report.summary + report.decisions + report.open_questions + report.risks
    assert all(c.checks.quotes_match and c.checks.references_valid for c in claims)


async def test_chat_recognizes_task_ownership_from_an_explicit_assignment():
    texts = [
        "We are keeping those choices for the first release.",
        "The landing page is ready for review, but we agreed to wait for the accessibility review",
        "before releasing it.",
        "They are part of one review, not separate assignments.",
        "Alex will complete the accessibility review tomorrow.",
        "This is the only review assignment from this meeting.",
        "There is no confirmed launch date.",
        "Tomorrow is the deadline for the accessibility review, not a promise to launch the website.",
    ]
    segments = [
        Segment(id=f"S{i}", start=i * 10, end=i * 10 + 5, text=text)
        for i, text in enumerate(texts, 1)
    ]
    result = await answer_question(
        Ollama(Settings()), "Who owns the accessibility review?", segments
    )
    assert result.supported
    assert "Alex" in result.answer
    assert any(s.segment_id == "S5" for s in result.citations)


async def test_self_assignments_use_voices_without_naming_a_nonparticipant_speaker():
    segments = [
        Segment(
            id="S1",
            start=0,
            end=4,
            text="Alex will prepare the launch copy tomorrow.",
            speaker_id="speaker_0",
        ),
        Segment(
            id="S2",
            start=5,
            end=9,
            text="I'll check the keyboard navigation tomorrow.",
            speaker_id="speaker_1",
        ),
        Segment(
            id="S3",
            start=10,
            end=14,
            text="I'll prepare the launch checklist tomorrow.",
            speaker_id="speaker_0",
        ),
    ]
    draft = await Ollama(Settings()).extract(segments, "en")
    report = ground_report(draft, segments, date(2026, 9, 11))
    root = Path(os.getenv("MEGAN_MODEL_RESULTS", ".local/evaluation/model-cases"))
    root.mkdir(parents=True, exist_ok=True)
    (root / "speaker-assignments-draft.json").write_text(draft.model_dump_json(indent=2))
    (root / "speaker-assignments.json").write_text(report.model_dump_json(indent=2))
    assert len(report.action_items) == 3
    by_source = {a.evidence["task"][0].segment_id: a for a in report.action_items}
    assert (by_source["S1"].assignee, by_source["S1"].speaker_id) == ("Alex", None)
    assert (by_source["S2"].assignee, by_source["S2"].speaker_id) == (None, "speaker_1")
    assert (by_source["S3"].assignee, by_source["S3"].speaker_id) == (None, "speaker_0")
