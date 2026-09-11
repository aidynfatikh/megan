"""Mechanical evidence checks, explicitly not a semantic truth verifier."""

import re
import unicodedata
from datetime import date

from backend.pipeline.dates import resolve_due
from backend.schemas import (
    Action,
    Checks,
    Claim,
    DraftReport,
    Due,
    Evidence,
    Report,
    Review,
    Segment,
    Source,
    Topic,
)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).casefold().strip()


PRIORITY_CUES = {
    "high": r"\b(?:high priority|urgent|высок\w* приоритет\w*|срочно|срочный|шұғыл|жоғары басымдық)\b",
    "normal": r"\b(?:normal priority|medium priority|обычн\w* приоритет\w*|средн\w* приоритет\w*|қалыпты басымдық)\b",
    "low": r"\b(?:low priority|низк\w* приоритет\w*|төмен басымдық)\b",
}


def explicit_priority(priority, sources):
    # Conservative lexical support, not a semantic classifier. Ambiguity stays unknown.
    for source in sources:
        text = normalize(source.quote)
        if re.search(r"\b(?:not|never|не|нет|емес|жоқ)\b", text):
            continue
        if re.search(PRIORITY_CUES[priority], text):
            return True
    return False


def negates_date(text, raw):
    wording = re.escape(normalize(raw))
    return bool(
        re.search(rf"\b(?:not|не)\s+{wording}(?:\b|$)|{wording}\s+(?:емес|жоқ)\b", normalize(text))
    )


def first_person_commitment(quote):
    # Only a lexical cue; all voice-based task ownership remains marked for review.
    return bool(re.match(r"^(?:i(?:['’]ll|\s+will)\b|я\b|мен\b)", normalize(quote).lstrip('"“«')))


# Whisper splits continuous speech at arbitrary points, so a model quoting one spoken phrase
# can legitimately cross a segment boundary. Such a quote is still grounded: the words must run
# contiguously and must begin in the cited segment, which stays far stricter than searching the
# whole meeting. Without this, a formatting artifact was indistinguishable from invention and
# discarded the owner and deadline it carried.
SPAN_MAX_SEGMENTS = 4
SPAN_MAX_GAP_SEC = 2.0

# A claim is only as good as the words backing it. Single common tokens such as "и" appear in
# almost every segment and support nothing, so thin claim evidence is surfaced for review. Action
# fields keep their own stricter test: the owner, date or priority must appear inside the quote.
MIN_CLAIM_QUOTE_CHARS = 10


def matching_span(quote: str, segments: dict[str, Segment], segment_id: str) -> Segment | None:
    """Return the last segment a contiguous quote covers, or None when it is unsupported."""
    wanted = normalize(quote)
    if not wanted:
        return None
    ordered = list(segments.values())
    start = next((i for i, s in enumerate(ordered) if s.id == segment_id), None)
    if start is None:
        return None
    joined = normalize(ordered[start].text)
    if wanted in joined:
        return ordered[start]
    for index in range(start + 1, min(start + SPAN_MAX_SEGMENTS, len(ordered))):
        if ordered[index].start - ordered[index - 1].end > SPAN_MAX_GAP_SEC:
            break
        joined = f"{joined} {normalize(ordered[index].text)}"
        if wanted in joined:
            return ordered[index]
    return None


def check_sources(evidence: list[Evidence], segments: dict[str, Segment], field: str):
    sources, reasons = [], []
    refs_valid = quotes_match = bool(evidence)
    if not evidence:
        reasons.append(f"missing_evidence:{field}")
    for entry in evidence:
        segment = segments.get(entry.segment_id)
        last = None
        if segment is None:
            refs_valid = quotes_match = False
            reasons.append(f"invalid_reference:{field}")
        else:
            last = matching_span(entry.quote, segments, entry.segment_id)
            if last is None:
                quotes_match = False
                reasons.append(f"quote_mismatch:{field}")
            elif field == "claim" and len(normalize(entry.quote)) < MIN_CLAIM_QUOTE_CHARS:
                reasons.append(f"weak_evidence:{field}")
        sources.append(
            Source(
                **entry.model_dump(),
                start=segment.start if segment else None,
                end=(last or segment).end if segment else None,
            )
        )
    return sources, Checks(references_valid=refs_valid, quotes_match=quotes_match), reasons


def ground_report(
    draft: DraftReport, transcript: list[Segment], meeting_date: date | None
) -> Report:
    segments = {s.id: s for s in transcript}

    def claim(entry, item_id):
        sources, checks, reasons = check_sources(entry.evidence, segments, "claim")
        return Claim(
            id=item_id,
            text=entry.text,
            evidence=sources,
            checks=checks,
            review=Review(state="needs_review" if reasons else "unreviewed", reasons=reasons),
        )

    report = Report(
        title=draft.title,
        summary=[claim(c, f"SUM{i}") for i, c in enumerate(draft.summary, 1)],
        topics=[
            Topic(
                id=f"T{i}",
                title=t.title,
                theses=[claim(c, f"T{i}.{j}") for j, c in enumerate(t.theses, 1)],
            )
            for i, t in enumerate(draft.topics, 1)
        ],
        decisions=[claim(c, f"D{i}") for i, c in enumerate(draft.decisions, 1)],
        open_questions=[claim(c, f"Q{i}") for i, c in enumerate(draft.open_questions, 1)],
        risks=[claim(c, f"R{i}") for i, c in enumerate(draft.risks, 1)],
    )
    for i, entry in enumerate(draft.action_items, 1):
        evidence, checks_by_field, reasons = {}, {}, []
        fields = ["task"]
        if entry.assignee or entry.speaker_id or entry.evidence.assignee:
            fields.append("assignee")
        if entry.due_raw:
            fields.append("due")
        if entry.priority != "unspecified":
            fields.append("priority")
        for field in fields:
            entries = getattr(entry.evidence, field)
            if field == "assignee" and not entries and entry.assignee:
                for source in entry.evidence.task:
                    segment = segments.get(source.segment_id)
                    if (
                        segment
                        and normalize(source.quote)
                        and normalize(source.quote) in normalize(segment.text)
                        and normalize(entry.assignee) in normalize(source.quote)
                    ):
                        entries = [source]
                        reasons.append("assignee_evidence_from_task_quote")
                        break
            if (
                field == "due"
                and entry.due_raw
                and (
                    not entries
                    or (
                        all(
                            s.segment_id in segments
                            and normalize(s.quote)
                            and normalize(s.quote) in normalize(segments[s.segment_id].text)
                            for s in entries
                        )
                        and not any(normalize(entry.due_raw) in normalize(s.quote) for s in entries)
                    )
                )
            ):
                # Reuse only the exact deadline inside an already valid task quote.
                # Never search unrelated turns or repair a supplied invalid citation.
                for source in entry.evidence.task:
                    segment = segments.get(source.segment_id)
                    if (
                        segment
                        and normalize(source.quote)
                        and normalize(source.quote) in normalize(segment.text)
                        and normalize(entry.due_raw) in normalize(source.quote)
                        and not negates_date(segment.text, entry.due_raw)
                    ):
                        entries = list(entries) + [
                            Evidence(segment_id=source.segment_id, quote=entry.due_raw)
                        ]
                        reasons.append("due_evidence_from_task_quote")
                        break
            evidence[field], checks_by_field[field], issues = check_sources(
                entries, segments, field
            )
            reasons.extend(issues)
        for field in ("assignee", "due", "priority"):
            evidence.setdefault(field, [])

        def supported(field, value=None, checks_by_field=checks_by_field, evidence=evidence):
            checks = checks_by_field.get(field)
            if not checks or not checks.references_valid or not checks.quotes_match:
                return False
            return value is None or any(
                normalize(value) in normalize(s.quote) for s in evidence[field]
            )

        assignee = entry.assignee
        if assignee and not supported("assignee", assignee):
            assignee = None
            reasons.append("unsupported_assignee")

        def within_cited_segment(source, segments=segments):
            # A quote that continued into later segments cannot fix a voice: the first-person
            # wording may belong to whoever spoke the continuation.
            segment = segments.get(source.segment_id)
            return segment is not None and source.end == segment.end

        speaker_id = entry.speaker_id
        generic_owner = entry.assignee is None or bool(
            re.fullmatch(r"(?:speaker|говорящий|сөйлеуші)[ _-]*\d+", normalize(entry.assignee))
        )
        if generic_owner and speaker_id is None and supported("assignee"):
            quoted_voices = {segments[s.segment_id].speaker_id for s in evidence["assignee"]}
            if (
                len(quoted_voices) == 1
                and None not in quoted_voices
                and all(within_cited_segment(s) for s in evidence["assignee"])
                and any(first_person_commitment(s.quote) for s in evidence["assignee"])
            ):
                speaker_id = next(iter(quoted_voices))
                assignee = None
                reasons.append("speaker_id_from_owner_quote")
        if speaker_id and (
            not generic_owner
            or not supported("assignee")
            or not all(
                segments[s.segment_id].speaker_id == speaker_id and within_cited_segment(s)
                for s in evidence["assignee"]
                if s.segment_id in segments
            )
            or not any(first_person_commitment(s.quote) for s in evidence["assignee"])
        ):
            speaker_id = None
            reasons.append("unsupported_speaker")
        elif speaker_id:
            # A voice label and first-person wording still need semantic/audio review.
            reasons.append("speaker_assignment_needs_review")
        due = resolve_due(entry.due_raw, meeting_date)
        if entry.due_raw and (
            not supported("due", entry.due_raw)
            or any(
                negates_date(segments[s.segment_id].text, entry.due_raw)
                for s in evidence["due"]
                if s.segment_id in segments
            )
        ):
            due = Due(raw=entry.due_raw, resolution="unsupported")
            reasons.append("unsupported_due")
        elif due.resolution in ("ambiguous", "needs_meeting_date"):
            reasons.append(f"due:{due.resolution}")
        priority = entry.priority
        if priority != "unspecified" and not (
            supported("priority") and explicit_priority(priority, evidence["priority"])
        ):
            priority = "unspecified"
            reasons.append("unsupported_priority")
        report.action_items.append(
            Action(
                id=f"A{i}",
                task=entry.task,
                assignee=assignee,
                speaker_id=speaker_id,
                due=due,
                priority=priority,
                conditions=entry.conditions,
                evidence=evidence,
                checks=Checks(
                    references_valid=all(c.references_valid for c in checks_by_field.values()),
                    quotes_match=all(c.quotes_match for c in checks_by_field.values()),
                ),
                review=Review(
                    state="needs_review" if reasons else "unreviewed",
                    reasons=list(dict.fromkeys(reasons)),
                ),
            )
        )
    return report
