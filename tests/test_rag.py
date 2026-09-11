from unittest.mock import AsyncMock

from backend.pipeline.rag import answer_question, retrieve
from backend.schemas import ChatDraft, Evidence, Segment


async def test_chat_rejects_fabricated_citations():
    ollama = AsyncMock()
    ollama.answer.return_value = ChatDraft(
        answer="Launch Friday", evidence=[Evidence(segment_id="S99", quote="Launch Friday")]
    )
    answer = await answer_question(
        ollama, "When do we launch?", [Segment(id="S1", start=0, end=2, text="No launch date yet.")]
    )
    assert not answer.supported
    assert answer.citations == []


async def test_chat_derives_source_time_from_transcript():
    ollama = AsyncMock()
    ollama.answer.return_value = ChatDraft(
        answer="Alex", evidence=[Evidence(segment_id="S1", quote="Alex will review it")]
    )
    answer = await answer_question(
        ollama,
        "Who will review it?",
        [Segment(id="S1", start=7, end=9, text="Alex will review it tomorrow.")],
    )
    assert answer.supported
    assert answer.citations[0].start == 7


async def test_no_relevant_excerpts_skips_inference_for_long_meetings():
    ollama = AsyncMock()
    segments = [
        Segment(id=f"S{i}", start=i, end=i + 1, text="We discussed the design") for i in range(20)
    ]
    answer = await answer_question(ollama, "Did someone order pizza?", segments)
    assert not answer.supported
    ollama.answer.assert_not_called()


def test_retrieval_keeps_the_best_match_over_earlier_weak_hits():
    """The strongest turn must survive the limit even when it is spoken last."""

    def segment(index: int, text: str):
        return Segment(id=f"S{index + 1}", start=float(index), end=index + 1.0, text=text)

    segments = [segment(i, "Ничего важного не прозвучало") for i in range(40)]
    for index in (3, 9, 15):
        segments[index] = segment(index, "бюджет")
    segments[35] = segment(35, "бюджет проекта утверждён сорок миллионов бюджет проекта")

    selected = retrieve("Какой бюджет проекта утверждён?", segments)

    assert len(selected) <= 8
    assert "S36" in {s.id for s in selected}
    assert [s.start for s in selected] == sorted(s.start for s in selected)


def test_retrieval_matches_inflected_russian_forms():
    """A question asking about "бюджету" must reach a turn that says "бюджет"."""
    filler = [
        Segment(id=f"S{i}", start=float(i), end=i + 1.0, text="Ничего важного не прозвучало")
        for i in range(1, 20)
    ]
    answer = Segment(id="S20", start=20.0, end=21.0, text="Бюджет утверждён в полном объёме")

    selected = retrieve("Что решили по бюджету?", [*filler, answer])

    assert "S20" in {s.id for s in selected}


def test_retrieval_does_not_match_unrelated_short_prefixes():
    filler = [
        Segment(id=f"S{i}", start=float(i), end=i + 1.0, text="Ничего важного не прозвучало")
        for i in range(1, 20)
    ]
    unrelated = Segment(id="S20", start=20.0, end=21.0, text="Раз два три")

    assert retrieve("Пицца?", [*filler, unrelated]) == []
