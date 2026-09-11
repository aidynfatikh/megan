import re
from collections import Counter

from backend.pipeline.structure import Ollama
from backend.pipeline.validate import check_sources
from backend.schemas import ChatAnswer, Segment

STOPWORDS = set(
    "what who when where why how did does do the a an is are was were to for of about in on and что кто когда где как это о об и в на по с из ли сказал said meeting встрече".split()
)


def tokens(text):
    return [w for w in re.findall(r"\w+", text.casefold()) if w not in STOPWORDS and len(w) > 1]


def retrieve(question: str, segments: list[Segment], limit=8):
    query = set(tokens(question))
    scores = []
    for index, segment in enumerate(segments):
        words = Counter(tokens(segment.text))
        score = sum(min(words[word], 2) for word in query)
        if score:
            scores.append((score, index))
    indexes = set()
    for _, index in sorted(scores, reverse=True)[:4]:
        indexes.update(range(max(0, index - 1), min(len(segments), index + 2)))
    # Full short meetings avoid losing follow-up context to keyword mismatch.
    if len(segments) <= limit:
        return segments
    return [segments[i] for i in sorted(indexes)[:limit]]


async def answer_question(ollama: Ollama, question: str, segments: list[Segment]) -> ChatAnswer:
    selected = retrieve(question, segments)
    if not selected:
        return ChatAnswer(answer="Not found in this meeting.", citations=[], supported=False)
    result = await ollama.answer(question, selected)
    citations, checks, _ = check_sources(result.evidence, {s.id: s for s in selected}, "answer")
    if not checks.references_valid or not checks.quotes_match:
        return ChatAnswer(
            answer="Not found in this meeting with a matching source.",
            citations=[],
            supported=False,
        )
    return ChatAnswer(answer=result.answer, citations=citations, supported=True)
