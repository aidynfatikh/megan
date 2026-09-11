import csv
import io
from datetime import UTC, datetime

from backend.schemas import Report


def safe_cell(value) -> str:
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def export_csv(report: Report) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "assignee",
            "task",
            "due",
            "due_raw",
            "priority",
            "conditions",
            "timestamp",
            "quote",
            "review",
        ]
    )
    for item in report.action_items:
        source = next(iter(item.evidence.get("task", [])), None)
        writer.writerow(
            [
                safe_cell(v)
                for v in (
                    item.id,
                    item.assignee,
                    item.task,
                    item.due.date,
                    item.due.raw,
                    item.priority,
                    "; ".join(item.conditions),
                    source.start if source else None,
                    source.quote if source else None,
                    item.review.state,
                )
            ]
        )
    return output.getvalue().encode("utf-8-sig")


def ical_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r", "")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def fold_line(line: str) -> str:
    parts, part = [], ""
    for char in line:
        if len((part + char).encode("utf-8")) > 75:
            parts.append(part)
            part = " "
        part += char
    parts.append(part)
    return "\r\n".join(parts)


def export_ics(report: Report, job_id: str) -> tuple[bytes, int]:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Megan//Local Meeting Intelligence//EN",
        "CALSCALE:GREGORIAN",
    ]
    skipped = 0
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    for item in report.action_items:
        if item.due.date is None:
            skipped += 1
            continue
        lines.extend(
            [
                "BEGIN:VTODO",
                f"UID:{job_id}-{item.id}@megan.local",
                f"DTSTAMP:{stamp}",
                f"SUMMARY:{ical_text(item.task)}",
                f"DUE;VALUE=DATE:{item.due.date:%Y%m%d}",
                f"DESCRIPTION:{ical_text('Owner: ' + (item.assignee or 'Unspecified'))}",
                "STATUS:NEEDS-ACTION",
                "END:VTODO",
            ]
        )
    lines.append("END:VCALENDAR")
    return ("\r\n".join(fold_line(line) for line in lines) + "\r\n").encode("utf-8"), skipped
