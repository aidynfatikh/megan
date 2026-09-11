from datetime import date

import pytest

from backend.pipeline.dates import resolve_due


@pytest.mark.parametrize(
    ("raw", "meeting_date", "expected", "resolution"),
    [
        (None, date(2026, 9, 11), None, "not_stated"),
        ("tomorrow", date(2026, 9, 11), date(2026, 9, 12), "relative"),
        ("завтра", date(2026, 12, 31), date(2027, 1, 1), "relative"),
        ("ертең", date(2026, 9, 11), date(2026, 9, 12), "relative"),
        ("послезавтра", date(2028, 2, 28), date(2028, 3, 1), "relative"),
        ("бүгін", date(2026, 9, 11), date(2026, 9, 11), "relative"),
        ("через 3 дня", date(2026, 9, 11), date(2026, 9, 14), "relative"),
        ("in 2 days", date(2026, 9, 11), date(2026, 9, 13), "relative"),
        ("3 күннен кейін", date(2026, 9, 11), date(2026, 9, 14), "relative"),
        ("2026-09-18", None, date(2026, 9, 18), "explicit"),
        ("до 18.09.2026", None, date(2026, 9, 18), "explicit"),
        ("by September 18, 2026", None, date(2026, 9, 18), "explicit"),
        ("18 сентября 2026 года", None, date(2026, 9, 18), "explicit"),
        ("2026 жылғы 18 қыркүйек", None, date(2026, 9, 18), "explicit"),
        ("September 18", None, None, "needs_meeting_date"),
        # 2026-09-11 is itself a Friday: the speaker could mean today or the next one.
        ("до пятницы", date(2026, 9, 11), None, "ambiguous"),
        # 2026-09-10 is a Thursday, so the intended Friday is determinate.
        ("Friday", date(2026, 9, 10), date(2026, 9, 11), "relative"),
        ("до пятницы", date(2026, 9, 7), date(2026, 9, 11), "relative"),
        ("жұмаға дейін", date(2026, 9, 7), date(2026, 9, 11), "relative"),
        ("в понедельник", date(2026, 9, 11), date(2026, 9, 14), "relative"),
        # "next Friday" is the genuinely ambiguous English form and must stay raw.
        ("next friday", date(2026, 9, 7), None, "ambiguous"),
        ("до 18 сентября", date(2026, 9, 11), date(2026, 9, 18), "relative"),
        ("18 қыркүйек", date(2026, 9, 11), date(2026, 9, 18), "relative"),
        # A day/month already past rolls to the next occurrence, never backwards.
        ("1 марта", date(2026, 9, 11), date(2027, 3, 1), "relative"),
        ("September 18", date(2026, 9, 11), date(2026, 9, 18), "relative"),
        # Kazakh Saturday must not be matched inside Monday/Tuesday/Wednesday/Thursday/Sunday.
        ("сенбі", date(2026, 9, 11), date(2026, 9, 12), "relative"),
        ("дүйсенбі", date(2026, 9, 11), date(2026, 9, 14), "relative"),
        ("завтра", None, None, "needs_meeting_date"),
        ("скоро", date(2026, 9, 11), None, "ambiguous"),
        ("2026-02-30", None, None, "ambiguous"),
        ("не завтра, а после согласования", date(2026, 9, 11), None, "ambiguous"),
        ("2026-09-11 or 2026-09-12", None, None, "ambiguous"),
    ],
)
def test_dates_do_not_invent_calendar_context(raw, meeting_date, expected, resolution):
    result = resolve_due(raw, meeting_date)
    assert result.date == expected
    assert result.resolution == resolution
    assert result.raw == raw
