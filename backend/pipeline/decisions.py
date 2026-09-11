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
        if not quote or text.count(quote) != 1 or HYPOTHETICAL.search(text):
            continue
        offset = text.index(quote)
        for match in ADOPTION.finditer(quote):
            before, after = text[: offset + match.start()], text[offset + match.end() :]
            if NEGATED.search(before) or re.search(r"\bwould\s+(?:have\s+)?$", before):
                continue
            if re.match(r"\s+(?:бы|емес|жоқ)\b", after):
                continue
            return True
    return False
