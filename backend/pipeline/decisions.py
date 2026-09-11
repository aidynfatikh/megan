"""Conservative lexical support for explicit adoption, not a semantic truth check."""

import re

from backend.pipeline.evidence import normalize

ADOPTION = re.compile(
    r"\b(?:agreed|decided|approved|adopted|voted|settled on|(?:we|i) agree|"
    r"решили|решено|договорились|согласовали|согласовано|утвердили|утвержден[аоы]?|"
    r"выбрали|приняли решение|бекітілді|бекіттік|келістік|келісілді|шештік|шешім қабылдадық)\b"
)
NEGATED = re.compile(
    r"\b(?:not|never|haven['’]t|hadn['’]t|didn['’]t|don['’]t|не)\s+(?:\w+\s+){0,2}$"
)
HYPOTHETICAL = re.compile(r"^(?:if|suppose|imagine|если|допустим|егер)\b")


def has_explicit_adoption(sources, segments):
    for source in sources:
        quote = normalize(source.quote)
        text = normalize(segments[source.segment_id].text)
        words = re.findall(r"\w+", quote)
        if not words or HYPOTHETICAL.search(text):
            continue
        pattern = r"(?<!\w)" + r"[\W_]+".join(re.escape(w) for w in words) + r"(?!\w)"
        placements = list(re.finditer(pattern, text))
        if len(placements) != 1:
            continue
        placement = placements[0]
        # Match adoption in the full original segment: "agreed" inside "disagreed"
        # is not an agreement, and a shortened quote cannot hide preceding negation.
        for match in ADOPTION.finditer(text):
            if match.start() < placement.start() or match.end() > placement.end():
                continue
            before, after = text[: match.start()], text[match.end() :]
            if NEGATED.search(before) or re.search(r"\bwould\s+(?:have\s+)?$", before):
                continue
            if re.match(r"\s+(?:бы|емес|жоқ)\b", after):
                continue
            return True
    return False
