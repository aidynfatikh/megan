"""Split a long transcript into windows that each fit the report prompt.

Splitting happens on segment boundaries, so evidence identifiers and timestamps stay global and
every quotation still refers to the same segment it came from. Windows overlap slightly, because
a commitment stated at the end of one window is often qualified at the start of the next; the
merge step removes the resulting duplicates.
"""

from backend.config import Settings
from backend.pipeline.context import prompt_tokens
from backend.pipeline.structure import extraction_messages
from backend.schemas import Segment

# Carried into the next window so a sentence split across a boundary keeps its context.
OVERLAP_SEGMENTS = 2


def budget(settings: Settings) -> int:
    return settings.llm_context - settings.llm_output_tokens - 256


def plan_chunks(
    segments: list[Segment], settings: Settings, language: str, reserve: int = 0
) -> list[list[Segment]]:
    """Return windows that each fit the prompt budget, in chronological order."""
    if not segments:
        return []
    limit = budget(settings) - reserve
    empty = prompt_tokens(extraction_messages([], language), settings)
    costs = [
        prompt_tokens(extraction_messages([segment], language), settings) - empty
        for segment in segments
    ]
    if limit <= empty:
        raise ValueError("The configured context leaves no room for a transcript")

    chunks: list[list[Segment]] = []
    index = 0
    while index < len(segments):
        window: list[Segment] = []
        used = empty
        while index < len(segments) and (not window or used + costs[index] <= limit):
            # A single segment larger than the whole budget still has to go somewhere; it is
            # placed alone and the prompt bound reports it rather than looping forever.
            window.append(segments[index])
            used += costs[index]
            index += 1
        # Per-segment costs ignore merges across joins, so confirm the assembled window.
        while (
            len(window) > 1
            and prompt_tokens(extraction_messages(window, language), settings) > limit
        ):
            index -= 1
            window.pop()
        chunks.append(window)
        if index < len(segments):
            # Step back for continuity, but never behind this window's own start, so the
            # cursor always advances and the loop terminates.
            first = index - len(window)
            index = max(index - OVERLAP_SEGMENTS, first + 1)
    return chunks
