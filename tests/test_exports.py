import csv
import io
from datetime import date

from backend.pipeline.export import export_csv, export_ics
from backend.pipeline.validate import ground_report
from backend.schemas import DraftReport, Segment


def report():
    data = {
        "title": "Смета",
        "summary": [],
        "topics": [],
        "decisions": [],
        "open_questions": [],
        "risks": [],
        "action_items": [],
    }
    for raw in ("завтра", "скоро"):
        data["action_items"].append(
            {
                "task": "=SUM(A1:A2)",
                "assignee": None,
                "speaker_id": None,
                "due_raw": raw,
                "priority": "unspecified",
                "conditions": [],
                "evidence": {
                    "assignee": [],
                    "priority": [],
                    "task": [{"segment_id": "S1", "quote": "Смета"}],
                    "due": [{"segment_id": "S1", "quote": raw}],
                },
            }
        )
    return ground_report(
        DraftReport.model_validate(data),
        [Segment(id="S1", start=3, end=4, text="Смета завтра или скоро")],
        date(2026, 9, 11),
    )


def test_csv_preserves_unicode_and_neutralizes_spreadsheet_formulas():
    rows = list(csv.DictReader(io.StringIO(export_csv(report()).decode("utf-8-sig"))))
    assert rows[0]["task"].startswith("'=")
    assert rows[0]["due"] == "2026-09-12"
    assert rows[1]["due"] == ""
    assert rows[1]["due_raw"] == "скоро"


def test_ics_uses_tasks_with_due_dates_without_inventing_meeting_times():
    content, skipped = export_ics(report(), "job-1")
    text = content.decode()
    assert skipped == 1
    assert "BEGIN:VTODO" in text
    assert "DUE;VALUE=DATE:20260912" in text
    assert "UID:job-1-A1@megan.local" in text
    assert "DTSTART" not in text
    assert text.count("BEGIN:VTODO") == 1


def test_exports_preserve_anonymous_speaker_owners_shown_in_the_ui():
    from backend.schemas import Speaker

    value = report()
    value.action_items[0].speaker_id = "speaker_0"
    speakers = [Speaker(id="speaker_0", name="Speaker 1")]
    rows = list(csv.DictReader(io.StringIO(export_csv(value, speakers).decode("utf-8-sig"))))
    assert rows[0]["assignee"] == "Speaker 1"
    assert rows[0]["speaker_id"] == "speaker_0"
    content, _ = export_ics(value, "job-1", speakers)
    assert "Owner: Speaker 1" in content.decode()
