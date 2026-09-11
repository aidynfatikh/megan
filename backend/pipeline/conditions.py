"""Recover a narrow, literal condition omitted immediately before a final task quote."""

import re

from backend.schemas import Evidence, Segment

PREFIX = re.compile(
    r"(?:^|[.!?]\s+)(?P<condition>(?:if|unless|provided that|as long as|если|егер)\b[^,.!?;\n]{1,200}),\s*",
    re.IGNORECASE,
)
CORRECTION = re.compile(
    r"\b(?:actually|instead|correction|regardless|unconditionally|no longer|"
    r"исправ\w*|вместо|отмен\w*|независимо|түзет\w*|қарамастан)\b",
    re.IGNORECASE,
)


def omitted_final_condition(evidence: list[Evidence], segments: dict[str, Segment]):
    # A later transcript turn might cancel the condition. Such cases stay with the
    # model/reviewer; this helper only handles one literal task quote in the final turn.
    if len(evidence) != 1 or not segments:
        return None
    source = evidence[0]
    segment = segments.get(source.segment_id)
    if segment is None or segment.id != max(segments.values(), key=lambda s: s.end).id:
        return None
    if not source.quote.strip():
        return None
    pattern = r"\s+".join(re.escape(w) for w in source.quote.split())
    occurrences = list(re.finditer(pattern, segment.text, re.IGNORECASE))
    if len(occurrences) != 1:
        return None
    quote = occurrences[0]
    for match in PREFIX.finditer(segment.text):
        if quote.start() != match.end():
            continue
        if CORRECTION.search(segment.text[quote.end() :]):
            return None
        return Evidence(segment_id=segment.id, quote=match["condition"])
    return None
