"""Invented, explicitly labeled report for UI exploration without model downloads."""

from datetime import UTC, date, datetime
from uuid import UUID

from backend.pipeline.validate import ground_report
from backend.schemas import DraftReport, Job, Provenance, Segment, Speaker


def example_job() -> Job:
    texts = [
        "The landing page is ready. We agreed to launch after the accessibility review.",
        "Alex will finish the accessibility review tomorrow. This is high priority.",
        "Mira will prepare the launch copy by 2026-09-18.",
        "We still need to choose an analytics provider. The launch is blocked until the accessibility review passes.",
        "We agreed to avoid paid analytics for the first release.",
    ]
    segments = [
        Segment(
            id=f"S{i}",
            start=(i - 1) * 12,
            end=i * 12,
            text=text,
            speaker_id=f"speaker_{(i - 1) % 3}",
            language="en",
        )
        for i, text in enumerate(texts, 1)
    ]

    def evidence(i, quote=None):
        return [{"segment_id": f"S{i}", "quote": quote or texts[i - 1]}]

    def claim(text, i):
        return {"text": text, "evidence": evidence(i)}

    draft = DraftReport.model_validate(
        {
            "title": "Website launch sync",
            "summary": [
                claim(
                    "The landing page is ready, with launch dependent on an accessibility review.",
                    1,
                ),
                claim(
                    "Alex owns the accessibility review, and Mira will prepare the launch copy.", 2
                ),
                claim(
                    "An analytics provider is still undecided; paid analytics will be excluded from the first release.",
                    5,
                ),
            ],
            "topics": [
                {
                    "title": "Launch readiness",
                    "theses": [claim("The accessibility review is a launch dependency.", 4)],
                },
                {"title": "Analytics", "theses": [claim("Provider selection remains open.", 4)]},
            ],
            "decisions": [
                claim("Launch after the accessibility review.", 1),
                claim("Keep paid analytics out of the first release.", 5),
            ],
            "open_questions": [claim("Which analytics provider should we use?", 4)],
            "risks": [claim("Launch is blocked until the accessibility review passes.", 4)],
            "action_items": [
                {
                    "task": "Complete the accessibility review",
                    "assignee": "Alex",
                    "speaker_id": "speaker_1",
                    "due_raw": "tomorrow",
                    "priority": "high",
                    "conditions": [],
                    "evidence": {
                        "task": evidence(2),
                        "assignee": evidence(2),
                        "due": evidence(2, "tomorrow"),
                        "priority": evidence(2, "high priority"),
                    },
                },
                {
                    "task": "Prepare launch copy",
                    "assignee": "Mira",
                    "speaker_id": "speaker_2",
                    "due_raw": "2026-09-18",
                    "priority": "unspecified",
                    "conditions": [],
                    "evidence": {
                        "task": evidence(3),
                        "assignee": evidence(3),
                        "due": evidence(3, "2026-09-18"),
                        "priority": [],
                    },
                },
            ],
        }
    )
    # Summary statements involving more than one source retain all supporting turns.
    draft.summary[1].evidence.extend(draft.action_items[1].evidence.task)
    draft.summary[2].evidence.extend(draft.open_questions[0].evidence)
    now = datetime(2026, 9, 11, 9, tzinfo=UTC)
    return Job(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        filename="Illustrative meeting — no audio",
        status="done",
        stage="done",
        created_at=now,
        updated_at=now,
        meeting_date=date(2026, 9, 11),
        report_language="en",
        duration_sec=60,
        segments=segments,
        speakers=[
            Speaker(id=f"speaker_{i}", name=name) for i, name in enumerate(["Dana", "Alex", "Mira"])
        ],
        report=ground_report(draft, segments, date(2026, 9, 11)),
        report_revision=1,
        provenance=Provenance(asr_backend="example", asr_model="none", llm="none", sample=True),
    )
