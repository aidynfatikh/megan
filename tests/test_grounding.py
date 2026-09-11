from datetime import date

from backend.pipeline.validate import ground_report
from backend.schemas import DraftReport, Segment


def source(segment_id="S1", quote="Дана отправит смету завтра."):
    return {"segment_id": segment_id, "quote": quote}


def draft(**overrides):
    data = {
        "title": "Обсуждение сметы",
        "summary": [],
        "topics": [],
        "decisions": [],
        "open_questions": [],
        "risks": [],
        "action_items": [
            {
                "task": "Отправить смету",
                "assignee": "Дана",
                "speaker_id": None,
                "due_raw": "завтра",
                "priority": "unspecified",
                "conditions": [],
                "evidence": {
                    "task": [source()],
                    "assignee": [source()],
                    "due": [source(quote="завтра")],
                    "priority": [],
                },
            }
        ],
    }
    data.update(overrides)
    return DraftReport.model_validate(data)


SEGMENTS = [Segment(id="S1", start=10, end=13, text="Дана отправит смету завтра.")]


def test_explicit_nonparticipant_is_allowed_and_deadline_is_resolved():
    report = ground_report(draft(), SEGMENTS, date(2026, 9, 11))
    item = report.action_items[0]
    assert item.assignee == "Дана"
    assert item.speaker_id is None
    assert item.due.date == date(2026, 9, 12)
    assert item.checks.quotes_match
    assert item.review.state == "unreviewed"
    assert "verified" not in item.model_dump()


def test_fabricated_citation_is_flagged_not_repaired_to_an_unrelated_segment():
    data = draft().model_dump()
    data["action_items"][0]["evidence"]["task"] = [source("S99")]
    item = ground_report(DraftReport.model_validate(data), SEGMENTS, None).action_items[0]
    assert not item.checks.references_valid
    assert "invalid_reference:task" in item.review.reasons


def test_valid_task_quote_does_not_validate_invented_owner_deadline_or_priority():
    data = draft().model_dump()
    data["action_items"][0].update(assignee="Марат", due_raw="2026-09-20", priority="high")
    data["action_items"][0]["evidence"].update(assignee=[], due=[], priority=[])
    item = ground_report(
        DraftReport.model_validate(data), SEGMENTS, date(2026, 9, 11)
    ).action_items[0]
    assert item.assignee is None
    assert item.due.date is None
    assert item.priority == "unspecified"
    assert "unsupported_assignee" in item.review.reasons
    assert "unsupported_due" in item.review.reasons
    assert "unsupported_priority" in item.review.reasons


def test_high_similarity_is_not_treated_as_a_matching_quote():
    data = draft().model_dump()
    data["action_items"][0]["evidence"]["task"] = [source(quote="Дана НЕ отправит смету завтра.")]
    item = ground_report(DraftReport.model_validate(data), SEGMENTS, None).action_items[0]
    assert not item.checks.quotes_match
    assert "quote_mismatch:task" in item.review.reasons


def test_deadline_or_matching_quote_does_not_make_a_task_high_priority():
    data = draft().model_dump()
    data["action_items"][0]["priority"] = "high"
    data["action_items"][0]["evidence"]["priority"] = [source()]
    item = ground_report(DraftReport.model_validate(data), SEGMENTS, None).action_items[0]
    assert item.priority == "unspecified"
    assert "unsupported_priority" in item.review.reasons


def test_unknown_values_and_empty_meetings_remain_empty():
    report = ground_report(draft(action_items=[]), SEGMENTS, None)
    assert report.action_items == []
    assert report.decisions == []
    assert report.summary == []


def test_summary_claims_are_also_checked():
    report = ground_report(
        draft(summary=[{"text": "Budget is approved", "evidence": [source("S99")]}]), SEGMENTS, None
    )
    assert report.summary[0].checks.references_valid is False


def test_source_times_come_from_transcript_not_the_llm():
    item = ground_report(draft(), SEGMENTS, None).action_items[0]
    assert item.evidence["task"][0].start == 10
    assert item.evidence["task"][0].end == 13


def test_omitted_deadline_citation_can_use_exact_words_in_valid_task_quote():
    data = draft().model_dump()
    data["action_items"][0]["evidence"]["due"] = []
    item = ground_report(
        DraftReport.model_validate(data), SEGMENTS, date(2026, 9, 11)
    ).action_items[0]
    assert item.due.date == date(2026, 9, 12)
    assert item.evidence["due"][0].quote == "завтра"
    assert item.review.state == "needs_review"
    assert "due_evidence_from_task_quote" in item.review.reasons


def test_deadline_is_never_recovered_from_an_unrelated_segment():
    data = draft().model_dump()
    data["action_items"][0]["due_raw"] = "2026-09-20"
    data["action_items"][0]["evidence"]["due"] = []
    segments = SEGMENTS + [
        Segment(id="S2", start=14, end=16, text="Meeting postponed to 2026-09-20")
    ]
    item = ground_report(
        DraftReport.model_validate(data), segments, date(2026, 9, 11)
    ).action_items[0]
    assert item.due.date is None


def test_negated_deadline_is_not_recovered_from_a_task_quote():
    data = draft().model_dump()
    quote = "Дана отправит смету не завтра, а после проверки."
    data["action_items"][0]["evidence"]["task"] = [source(quote=quote)]
    data["action_items"][0]["evidence"]["due"] = []
    item = ground_report(
        DraftReport.model_validate(data),
        [Segment(id="S1", start=0, end=2, text=quote)],
        date(2026, 9, 11),
    ).action_items[0]
    assert item.due.date is None


def test_missing_owner_citation_can_only_reuse_a_matching_task_quote():
    data = draft().model_dump()
    data["action_items"][0]["evidence"]["assignee"] = []
    item = ground_report(DraftReport.model_validate(data), SEGMENTS, None).action_items[0]
    assert item.assignee == "Дана"
    assert item.evidence["assignee"][0].quote == SEGMENTS[0].text
    assert "assignee_evidence_from_task_quote" in item.review.reasons
    assert item.review.state == "needs_review"


def test_partial_deadline_quote_can_be_supplemented_by_full_task_quote():
    data = draft().model_dump()
    text = "Дана отправит смету 2026-09-18."
    data["action_items"][0]["due_raw"] = "2026-09-18"
    data["action_items"][0]["evidence"]["task"] = [source(quote=text)]
    data["action_items"][0]["evidence"]["due"] = [source("S2", "Срок сметы — 18 сентября.")]
    segments = [
        Segment(id="S1", start=0, end=3, text=text),
        Segment(id="S2", start=4, end=6, text="Срок сметы — 18 сентября."),
    ]
    item = ground_report(DraftReport.model_validate(data), segments, None).action_items[0]
    assert item.due.date == date(2026, 9, 18)
    assert [e.segment_id for e in item.evidence["due"]] == ["S2", "S1"]
    assert "due_evidence_from_task_quote" in item.review.reasons


def test_named_assignee_is_not_linked_to_the_voice_that_mentions_them():
    data = draft().model_dump()
    data["action_items"][0]["speaker_id"] = "speaker_0"
    segments = [SEGMENTS[0].model_copy(update={"speaker_id": "speaker_0"})]
    item = ground_report(DraftReport.model_validate(data), segments, None).action_items[0]
    assert item.assignee == "Дана"
    assert item.speaker_id is None  # The speaker may be assigning work to Dana.


def test_invalid_owner_quote_cannot_link_a_task_to_a_real_speaker():
    data = draft().model_dump()
    data["action_items"][0].update(assignee=None, speaker_id="speaker_0")
    data["action_items"][0]["evidence"]["assignee"] = [source(quote="I'll do it.")]
    segments = [SEGMENTS[0].model_copy(update={"speaker_id": "speaker_0"})]
    item = ground_report(DraftReport.model_validate(data), segments, None).action_items[0]
    assert item.speaker_id is None


def test_self_assignment_keeps_anonymous_speaker_and_requires_review():
    data = draft().model_dump()
    data["action_items"][0].update(assignee=None, speaker_id="speaker_0", due_raw=None)
    quote = "I'll send the estimate."
    data["action_items"][0]["evidence"].update(
        task=[source(quote=quote)], assignee=[source(quote=quote)], due=[]
    )
    segments = [Segment(id="S1", start=1, end=3, text=quote, speaker_id="speaker_0")]
    item = ground_report(DraftReport.model_validate(data), segments, None).action_items[0]
    assert item.assignee is None
    assert item.speaker_id == "speaker_0"
    assert item.review.state == "needs_review"
    assert "speaker_assignment_needs_review" in item.review.reasons


def test_model_display_label_is_resolved_from_quoted_voice_not_its_guessed_number():
    data = draft().model_dump()
    data["action_items"][0].update(assignee="Speaker 0", speaker_id=None, due_raw=None)
    quote = "I'll send the estimate."
    data["action_items"][0]["evidence"].update(
        task=[source(quote=quote)], assignee=[source(quote=quote)], due=[]
    )
    segments = [Segment(id="S1", start=1, end=3, text=quote, speaker_id="speaker_1")]
    item = ground_report(DraftReport.model_validate(data), segments, None).action_items[0]
    assert (item.assignee, item.speaker_id) == (None, "speaker_1")
    assert item.review.state == "needs_review"
    assert "speaker_id_from_owner_quote" in item.review.reasons


def test_missing_speaker_id_is_not_recovered_from_third_person_or_unknown_voice():
    for quote, speaker in [
        ("Alex will send the estimate.", "speaker_0"),
        ("I'll send the estimate.", None),
    ]:
        data = draft().model_dump()
        data["action_items"][0].update(assignee="Speaker 1", speaker_id=None, due_raw=None)
        data["action_items"][0]["evidence"].update(
            task=[source(quote=quote)], assignee=[source(quote=quote)], due=[]
        )
        segments = [Segment(id="S1", start=1, end=3, text=quote, speaker_id=speaker)]
        item = ground_report(DraftReport.model_validate(data), segments, None).action_items[0]
        assert (item.assignee, item.speaker_id) == (None, None)
