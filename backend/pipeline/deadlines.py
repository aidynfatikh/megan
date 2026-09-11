"""Restore a translated relative date only from the task's own exact source."""

import re

from backend.pipeline.dates import OFFSETS
from backend.pipeline.evidence import normalize
from backend.schemas import DraftAction, Evidence, Segment

RELATIVE_WORDS = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in sorted(OFFSETS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def original_relative_deadline(entry: DraftAction, segments: dict[str, Segment]):
    raw = normalize(entry.due_raw or "")
    if raw not in OFFSETS or len(entry.evidence.task) != 1:
        return None
    task = entry.evidence.task[0]
    segment = segments.get(task.segment_id)
    if (
        not segment
        or not normalize(task.quote)
        or normalize(task.quote) not in normalize(segment.text)
    ):
        return None
    # Never replace arbitrary bad citations or references. Only the same translated
    # alias in the same task segment is eligible; missing evidence is also eligible.
    if any(
        e.segment_id != task.segment_id or normalize(e.quote) != raw for e in entry.evidence.due
    ):
        return None
    matches = list(RELATIVE_WORDS.finditer(task.quote))
    if len(matches) != 1:
        return None
    original = matches[0].group()
    if normalize(original) == raw or OFFSETS[normalize(original)] != OFFSETS[raw]:
        return None
    return Evidence(segment_id=task.segment_id, quote=original)
