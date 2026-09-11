"""Exact text alignment, including a quotation split across adjacent ASR segments."""

import re
import unicodedata

from backend.schemas import Evidence, Segment, Source

MAX_ADJACENT_SEGMENTS = 4


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).casefold().strip()


def comparable(text: str) -> str:
    """Normalize for quote matching, ignoring punctuation.

    Whisper invents the punctuation in a transcript; the speaker never dictated it. A model that
    quotes the same words while dropping a comma or an em dash was quoting real speech, so
    rejecting it means matching on an ASR artifact rather than on content. Punctuation becomes a
    space so that neighbouring words cannot be fused into one token.
    """
    stripped = "".join(
        " " if unicodedata.category(character).startswith("P") else character
        for character in unicodedata.normalize("NFKC", text)
    )
    return re.sub(r"\s+", " ", stripped).casefold().strip()


def adjacent_sources(entry: Evidence, segments: dict[str, Segment]) -> list[Source]:
    quote = comparable(entry.quote)
    if not quote or entry.segment_id not in segments:
        return []
    ordered = sorted(segments.values(), key=lambda s: (s.start, s.end))
    anchor = next(i for i, s in enumerate(ordered) if s.id == entry.segment_id)
    matches = {}
    for begin in range(max(0, anchor - MAX_ADJACENT_SEGMENTS + 1), anchor + 1):
        for end in range(
            max(anchor + 1, begin + 2), min(len(ordered), begin + MAX_ADJACENT_SEGMENTS) + 1
        ):
            window = ordered[begin:end]
            ids = [re.fullmatch(r"S(\d+)", s.id) for s in window]
            if not all(ids) or any(
                int(b[1]) != int(a[1]) + 1 for a, b in zip(ids, ids[1:], strict=False)
            ):
                continue
            if any(b.start - a.end > 2 for a, b in zip(window, window[1:], strict=False)):
                continue
            texts = [comparable(s.text) for s in window]
            joined = " ".join(texts)
            offset = joined.find(quote)
            while offset >= 0:
                stop, cursor, sources = offset + len(quote), 0, []
                for segment, text in zip(window, texts, strict=True):
                    left, right = max(offset, cursor), min(stop, cursor + len(text))
                    if left < right:
                        fragment = text[left - cursor : right - cursor].strip()
                        if fragment:
                            # Preserve original case/spacing wherever possible. NFKC matching
                            # retains the existing canonical-text comparison semantics.
                            pattern = r"\W+".join(re.escape(w) for w in fragment.split())
                            raw = re.search(pattern, segment.text, re.IGNORECASE)
                            sources.append(
                                Source(
                                    segment_id=segment.id,
                                    quote=raw[0] if raw else fragment,
                                    start=segment.start,
                                    end=segment.end,
                                )
                            )
                    cursor += len(text) + 1
                if len(sources) > 1 and any(s.segment_id == entry.segment_id for s in sources):
                    key = tuple((s.segment_id, s.quote) for s in sources)
                    matches[key] = sources
                offset = joined.find(quote, offset + 1)
    # Repeated/ambiguous passages do not justify choosing an arbitrary occurrence.
    return next(iter(matches.values())) if len(matches) == 1 else []
