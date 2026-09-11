import re

from backend.pipeline.structure import Ollama
from backend.pipeline.validate import check_sources
from backend.schemas import ChatAnswer, Segment, Speaker

STOPWORDS = set(
    "what who when where why how did does do the a an is are was were to for of about in on and что кто когда где как это о об и в на по с из ли сказал said meeting встрече".split()
)


# Russian and Kazakh inflect heavily, so "кредитовании" in a question must reach "кредитованию"
# in a turn. Comparing on a shared prefix keeps retrieval recall-biased: a surplus excerpt costs
# a few tokens, a missed one loses the answer. Requiring one form to contain the other only
# covers suffix ADDITION ("бюджет"/"бюджета"); Russian more often SUBSTITUTES an ending of the
# same length, so a shared stem is compared directly. Five characters keeps unrelated words
# apart ("проект"/"процесс" share only three), while four is allowed when it is one whole word,
# which recovers short stems such as "банк"/"банка".
STEM_MIN = 4
STEM_CONFIDENT = 5


def tokens(text):
    return [w for w in re.findall(r"\w+", text.casefold()) if w not in STOPWORDS and len(w) > 1]


def same_stem(word: str, other: str) -> bool:
    if word == other:
        return True
    shared = 0
    for left, right in zip(word, other, strict=False):
        if left != right:
            break
        shared += 1
    # Allow a single substituted ending on the shorter form, which is how short stems inflect.
    return shared >= STEM_CONFIDENT or (
        shared >= STEM_MIN and shared >= min(len(word), len(other)) - 1
    )


# Four seeds each contribute their own turn plus one neighbour on either side, so a limit below
# twelve silently discarded context the ranking had already chosen to include.
SEEDS = 4


def retrieve(question: str, segments: list[Segment], limit=SEEDS * 3):
    # Full short meetings avoid losing follow-up context to keyword mismatch.
    if len(segments) <= limit:
        return segments
    query = set(tokens(question))
    scores = []
    for index, segment in enumerate(segments):
        words = tokens(segment.text)
        score = sum(min(sum(1 for word in words if same_stem(term, word)), 2) for term in query)
        if score:
            scores.append((score, index))
    # Strongest match first, each seed followed by its immediate context. Insertion order is
    # relevance order, so trimming to the limit drops the weakest turns, never the latest ones.
    selected: dict[int, None] = {}
    for _, index in sorted(scores, key=lambda entry: (-entry[0], entry[1]))[:SEEDS]:
        for neighbour in (index, index - 1, index + 1):
            if 0 <= neighbour < len(segments):
                selected.setdefault(neighbour, None)
    # Restore chronological order so the model reads the excerpts as they were spoken.
    return [segments[i] for i in sorted(list(selected)[:limit])]


def speaker_scope(question: str, speakers: list[Speaker]) -> set[str] | None:
    """Resolve explicit voice labels and named speech questions, not named task owners.

    Display ordinals are one-based; stored IDs are opaque. Unknown ordinals produce an
    empty scope rather than falling back to a different speaker's words.
    """
    text = question.casefold()
    labels = re.findall(r"\b(?:speaker|спикер)\s+([0-9]+|[a-dа-г])\b", text)
    labels += re.findall(r"\b([0-9]+)[-\s]спикер\b", text)
    ids: set[str] = set()
    for label in labels:
        index = (
            int(label) - 1
            if label.isdigit()
            else ("abcd".index(label) if label in "abcd" else "абвг".index(label))
        )
        if not 0 <= index < len(speakers):
            return set()
        ids.add(speakers[index].id)
    if labels:
        return ids
    # A person's name in 'what must Dana do?' is an assignee, not the diarized author.
    if re.search(r"\b(?:say|said|says|mention\w*|сказ\w*|говор\w*|айт\w*)\b", text):
        for speaker in speakers:
            if re.search(r"(?<!\w)" + re.escape(speaker.name.casefold()) + r"(?!\w)", text):
                ids.add(speaker.id)
        if ids:
            # Duplicate display names cannot identify a voice reliably.
            names = [s.name.casefold() for s in speakers if s.id in ids]
            return ids if len(names) == len(set(names)) else set()
    return None


async def answer_question(
    ollama: Ollama,
    question: str,
    segments: list[Segment],
    speakers: list[Speaker] | None = None,
    speaker_id: str | None = None,
) -> ChatAnswer:
    speakers = speakers or []
    scope = {speaker_id} if speaker_id is not None else speaker_scope(question, speakers)
    candidates = segments if scope is None else [s for s in segments if s.speaker_id in scope]
    selected = retrieve(question, candidates)
    if not selected:
        return ChatAnswer(answer="Not found in this meeting.", citations=[], supported=False)
    result = await ollama.answer(question, selected, speakers)
    citations, checks, _ = check_sources(result.evidence, {s.id: s for s in selected}, "answer")
    if not checks.references_valid or not checks.quotes_match:
        return ChatAnswer(
            answer="Not found in this meeting with a matching source.",
            citations=[],
            supported=False,
        )
    return ChatAnswer(answer=result.answer, citations=citations, supported=True)
