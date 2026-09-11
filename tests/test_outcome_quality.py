from datetime import date

import pytest

from backend.pipeline.validate import check_sources, ground_report
from backend.schemas import DraftReport, Evidence, Segment


def report_with_action(text, **overrides):
    action = {
        "task": "Review the change",
        "assignee": None,
        "speaker_id": None,
        "due_raw": None,
        "priority": "unspecified",
        "conditions": [],
        "evidence": {
            "task": [{"segment_id": "S1", "quote": text}],
            "assignee": [],
            "due": [],
            "priority": [],
        },
        **overrides,
    }
    return DraftReport.model_validate(
        {
            "title": "Change review",
            "summary": [],
            "topics": [],
            "decisions": [],
            "open_questions": [],
            "risks": [],
            "action_items": [action],
        }
    )


@pytest.mark.parametrize(
    "text",
    [
        "Айдар проверит экспорт завтра.",
        "Mira will publish tomorrow.",
        "Айдар ертең есепті жібереді.",
    ],
)
def test_missing_date_with_relative_word_in_task_source_is_flagged_without_guessing(text):
    action = ground_report(
        report_with_action(text), [Segment(id="S1", start=0, end=5, text=text)], date(2026, 9, 11)
    ).action_items[0]
    assert action.due.date is None
    assert action.review.state == "needs_review"
    assert "possible_omitted_deadline" in action.review.reasons


def test_missing_date_warning_does_not_search_unrelated_transcript_turns():
    text = "Mira will publish the page."
    segments = [
        Segment(id="S1", start=0, end=5, text=text),
        Segment(id="S2", start=6, end=10, text="Tomorrow's weather is uncertain."),
    ]
    action = ground_report(report_with_action(text), segments, None).action_items[0]
    assert "possible_omitted_deadline" not in action.review.reasons


@pytest.mark.parametrize(
    "source_word,translated", [("tomorrow", "завтра"), ("ертең", "tomorrow"), ("сегодня", "today")]
)
def test_translated_relative_deadline_uses_original_word_in_valid_task_quote(
    source_word, translated
):
    text = f"Mira will publish the page {source_word}."
    draft = report_with_action(text, due_raw=translated)
    draft.action_items[0].evidence.due = [Evidence(segment_id="S1", quote=translated)]
    original = draft.model_dump()
    action = ground_report(
        draft, [Segment(id="S1", start=0, end=5, text=text)], date(2026, 9, 11)
    ).action_items[0]
    assert action.due.raw == source_word
    assert action.due.date == date(2026, 9, 11 if translated == "today" else 12)
    assert action.evidence["due"][0].quote == source_word
    assert action.checks.quotes_match
    assert "translated_deadline_from_task_quote" in action.review.reasons
    assert draft.model_dump() == original


@pytest.mark.parametrize(
    "text,reference,quote",
    [
        ("Mira will publish tomorrow.", "S99", "завтра"),
        ("Mira will publish tomorrow.", "S1", "invented date quote"),
        ("Mira will publish, not tomorrow.", "S1", "завтра"),
        ("Mira will review today and publish tomorrow.", "S1", "завтра"),
        ("Mira will publish the day after tomorrow.", "S1", "завтра"),
    ],
)
def test_translated_deadline_does_not_repair_unrelated_ambiguous_or_negated_evidence(
    text, reference, quote
):
    draft = report_with_action(text, due_raw="завтра")
    draft.action_items[0].evidence.due = [Evidence(segment_id=reference, quote=quote)]
    action = ground_report(
        draft, [Segment(id="S1", start=0, end=5, text=text)], date(2026, 9, 11)
    ).action_items[0]
    assert action.due.date is None


@pytest.mark.parametrize("anchor", ["S1", "S2"])
def test_quote_spanning_neighboring_segments_keeps_both_original_sources(anchor):
    segments = {
        "S1": Segment(id="S1", start=5, end=8, text="It looks like Albert proposed an"),
        "S2": Segment(id="S2", start=8, end=11, text="hour later, subject to confirmation."),
    }
    sources, checks, reasons = check_sources(
        [Evidence(segment_id=anchor, quote="Albert proposed an hour later")], segments, "claim"
    )
    assert checks.references_valid and checks.quotes_match
    assert [(s.segment_id, s.quote, s.start, s.end) for s in sources] == [
        ("S1", "Albert proposed an", 5, 8),
        ("S2", "hour later", 8, 11),
    ]
    assert "adjacent_segment_quote:claim" in reasons


@pytest.mark.parametrize("gap,second_id", [(20, "S2"), (0, "S3")])
def test_quote_alignment_cannot_bridge_missing_speech_or_distant_turns(gap, second_id):
    segments = {
        "S1": Segment(id="S1", start=0, end=2, text="Dana will"),
        second_id: Segment(id=second_id, start=2 + gap, end=4 + gap, text="send it tomorrow."),
    }
    _, checks, _ = check_sources(
        [Evidence(segment_id="S1", quote="Dana will send it tomorrow")], segments, "task"
    )
    assert not checks.quotes_match


def test_neighbor_match_must_include_the_cited_segment_and_preserve_negation():
    segments = {
        "S1": Segment(id="S1", start=0, end=2, text="Dana will not"),
        "S2": Segment(id="S2", start=2, end=4, text="send it tomorrow."),
    }
    for quote in ("send it tomorrow", "Dana will send it tomorrow"):
        _, checks, _ = check_sources([Evidence(segment_id="S1", quote=quote)], segments, "task")
        assert not checks.quotes_match


def test_neighbor_quote_with_two_possible_source_windows_stays_unmatched():
    segments = {
        "S1": Segment(id="S1", start=0, end=1, text="go"),
        "S2": Segment(id="S2", start=1, end=2, text="now go"),
        "S3": Segment(id="S3", start=2, end=3, text="now"),
    }
    _, checks, _ = check_sources([Evidence(segment_id="S2", quote="go now")], segments, "task")
    assert not checks.quotes_match


@pytest.mark.parametrize(
    "status", ["completed", "proposal", "hypothetical", "rejected", "superseded"]
)
def test_non_outstanding_work_does_not_become_an_action_item(status):
    text = "I have already implemented the change and added the validation charts."
    draft = report_with_action(text, status=status)
    result = ground_report(draft, [Segment(id="S1", start=0, end=3, text=text)], None)
    assert not result.action_items


def test_outstanding_conditional_assignment_remains_with_owner_and_deadline():
    text = "If QA passes, Mira will publish the page tomorrow."
    evidence = [Evidence(segment_id="S1", quote=text)]
    draft = report_with_action(
        text,
        status="outstanding",
        assignee="Mira",
        due_raw="tomorrow",
        conditions=["If QA passes"],
        evidence={"task": evidence, "assignee": evidence, "due": evidence, "priority": []},
    )
    result = ground_report(draft, [Segment(id="S1", start=0, end=4, text=text)], date(2026, 9, 11))
    assert len(result.action_items) == 1
    assert result.action_items[0].assignee == "Mira"
    assert result.action_items[0].due.date == date(2026, 9, 12)
    assert result.action_items[0].conditions == ["If QA passes"]


def test_first_person_recipient_is_not_the_task_owner():
    text = "So I'll check with Kai in our one-on-one later in the week."
    evidence = [Evidence(segment_id="S1", quote=text)]
    draft = report_with_action(
        text,
        task="Confirm the time with Kai",
        assignee="Kai",
        evidence={"task": evidence, "assignee": evidence, "due": [], "priority": []},
    )
    result = ground_report(
        draft, [Segment(id="S1", start=0, end=4, text=text, speaker_id="speaker_0")], None
    )
    item = result.action_items[0]
    assert item.assignee is None
    assert item.speaker_id == "speaker_0"
    assert item.review.state == "needs_review"


def test_missing_voice_evidence_can_reuse_its_exact_first_person_task_quote():
    text = "I'll check the keyboard navigation tomorrow."
    draft = report_with_action(text, speaker_id="speaker_1")
    item = ground_report(
        draft, [Segment(id="S1", start=0, end=4, text=text, speaker_id="speaker_1")], None
    ).action_items[0]
    assert item.speaker_id == "speaker_1"
    assert item.evidence["assignee"][0].quote == text
    assert "assignee_evidence_from_task_quote" in item.review.reasons


def test_partial_pronoun_and_guessed_voice_id_use_the_actual_task_source():
    text = "I'll check the keyboard navigation tomorrow."
    draft = report_with_action(
        text,
        assignee="Speaker 2",
        speaker_id="S1",
        evidence={
            "task": [Evidence(segment_id="S1", quote=text)],
            "assignee": [Evidence(segment_id="S1", quote="I")],
            "due": [],
            "priority": [],
        },
    )
    item = ground_report(
        draft, [Segment(id="S1", start=0, end=4, text=text, speaker_id="speaker_1")], None
    ).action_items[0]
    assert (item.assignee, item.speaker_id) == (None, "speaker_1")
    assert item.review.state == "needs_review"


def test_someone_addressed_during_a_mixed_turn_is_not_an_assignee():
    text = "I'll check with you. Go ahead, Albert, sorry."
    evidence = [Evidence(segment_id="S1", quote=text)]
    draft = report_with_action(
        text,
        assignee="Albert",
        evidence={"task": evidence, "assignee": evidence, "due": [], "priority": []},
    )
    item = ground_report(draft, [Segment(id="S1", start=0, end=4, text=text)], None).action_items[0]
    assert item.assignee is None
    assert item.speaker_id is None


def test_condition_without_a_source_is_explicitly_marked_for_review():
    text = "I'll reschedule the meeting next week."
    draft = report_with_action(text, conditions=["After my daughter arrives"])
    item = ground_report(draft, [Segment(id="S1", start=0, end=4, text=text)], None).action_items[0]
    assert item.review.state == "needs_review"
    assert "missing_evidence:conditions" in item.review.reasons
    assert not item.checks.quotes_match


def test_original_condition_can_reuse_a_valid_assignment_quote():
    text = "If QA passes, Mira will publish the page tomorrow."
    draft = report_with_action(text, conditions=["If QA passes"])
    item = ground_report(draft, [Segment(id="S1", start=0, end=4, text=text)], None).action_items[0]
    assert item.conditions == ["If QA passes"]
    assert item.evidence["conditions"][0].quote == "If QA passes"
    assert item.checks.quotes_match


@pytest.mark.parametrize(
    "text,quote,condition",
    [
        (
            "If the checksum matches, Nora will publish tomorrow.",
            "Nora will publish tomorrow",
            "If the checksum matches",
        ),
        (
            "Если проверка пройдёт, Дана отправит отчёт завтра.",
            "Дана отправит отчёт завтра",
            "Если проверка пройдёт",
        ),
        (
            "Егер тексеру сәтті өтсе, Айдар есепті ертең жібереді.",
            "Айдар есепті ертең жібереді",
            "Егер тексеру сәтті өтсе",
        ),
    ],
)
def test_a_condition_immediately_before_the_final_task_quote_is_not_lost(text, quote, condition):
    draft = report_with_action(quote)
    item = ground_report(draft, [Segment(id="S1", start=0, end=4, text=text)], None).action_items[0]
    assert item.conditions == [condition]
    assert item.evidence["conditions"][0].quote == condition
    assert "condition_from_task_context" in item.review.reasons
    assert not draft.action_items[0].conditions  # Original generation stays auditable.


def test_a_condition_is_not_taken_from_another_action_or_over_a_later_correction():
    quote = "Nora will publish tomorrow"
    texts = [
        "If QA passes, Lee will deploy. Nora will publish tomorrow.",
        "If QA passes, Nora will publish tomorrow. Actually, publish regardless of QA.",
    ]
    for text in texts:
        draft = report_with_action(quote)
        item = ground_report(
            draft, [Segment(id="S1", start=0, end=4, text=text)], None
        ).action_items[0]
        assert not item.conditions
    draft = report_with_action(quote)
    item = ground_report(
        draft,
        [
            Segment(id="S1", start=0, end=4, text="If QA passes, Nora will publish tomorrow."),
            Segment(id="S2", start=4, end=8, text="Correction: she will publish regardless of QA."),
        ],
        None,
    ).action_items[0]
    assert not item.conditions


def test_a_tentative_decision_is_not_exported_as_an_agreement():
    draft = report_with_action("We need to discuss the schedule.", status="proposal")
    draft = DraftReport.model_validate(
        {
            **draft.model_dump(),
            "decisions": [
                {
                    "status": "tentative",
                    "text": "Move the meeting an hour later",
                    "evidence": [
                        {"segment_id": "S1", "quote": "Maybe an hour later; we must ask Kai first."}
                    ],
                }
            ],
        }
    )
    result = ground_report(
        draft,
        [Segment(id="S1", start=0, end=4, text="Maybe an hour later; we must ask Kai first.")],
        None,
    )
    assert not result.decisions


@pytest.mark.parametrize(
    "text,keep",
    [
        ("We agreed to keep the existing logo.", True),
        ("We agreed not to buy another microphone.", True),
        ("Мы решили проводить демонстрацию на русском языке.", True),
        ("Жоба бюджеті бекітілді.", True),
        ("Start a meeting by reviewing the previous notes.", False),
        ("Первое, что мы должны решить, это кто будет модератором.", False),
        ("Кездесуді өткен тапсырмаларды тексеруден бастау керек.", False),
        ("I have already implemented the change and added the charts.", False),
        ("We have not agreed to change the schedule.", False),
        ("We haven’t agreed to change the schedule.", False),
        ("Мы пока не выбрали модератора.", False),
        ("If we agreed to that proposal, we would need another review.", False),
    ],
)
def test_confirmed_decisions_require_cited_adoption_not_advice_or_completed_work(text, keep):
    draft = report_with_action(text, status="completed")
    draft = DraftReport.model_validate(
        {
            **draft.model_dump(),
            "decisions": [
                {
                    "status": "confirmed",
                    "text": "Model's proposed decision",
                    "evidence": [{"segment_id": "S1", "quote": text}],
                }
            ],
        }
    )
    original = draft.model_dump()
    result = ground_report(draft, [Segment(id="S1", start=0, end=5, text=text)], None)
    assert bool(result.decisions) == keep
    assert draft.model_dump() == original


def test_decision_quote_cannot_hide_negation_just_before_quoted_adoption():
    text = "We have not agreed to change the schedule."
    draft = report_with_action(text, status="completed")
    draft = DraftReport.model_validate(
        {
            **draft.model_dump(),
            "decisions": [
                {
                    "status": "confirmed",
                    "text": "Change the schedule",
                    "evidence": [{"segment_id": "S1", "quote": "agreed to change the schedule"}],
                }
            ],
        }
    )
    assert not ground_report(draft, [Segment(id="S1", start=0, end=5, text=text)], None).decisions
