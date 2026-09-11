from unittest.mock import AsyncMock

from backend.pipeline.rag import answer_question
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
