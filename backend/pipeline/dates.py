"""Conservative date resolution: unsupported wording never becomes a guessed date."""

import re
from datetime import date, timedelta

from backend.schemas import Due

OFFSETS = {
    "today": 0,
    "сегодня": 0,
    "бүгін": 0,
    "tomorrow": 1,
    "завтра": 1,
    "ертең": 1,
    "the day after tomorrow": 2,
    "послезавтра": 2,
    "бүрсігүні": 2,
}
MONTHS = {
    name: month
    for names in (
        "january february march april may june july august september october november december",
        "января февраля марта апреля мая июня июля августа сентября октября ноября декабря",
        "қаңтар ақпан наурыз сәуір мамыр маусым шілде тамыз қыркүйек қазан қараша желтоқсан",
    )
    for month, name in enumerate(names.split(), 1)
}


def resolve_due(raw: str | None, meeting_date: date | None) -> Due:
    if raw is None or not raw.strip():
        return Due(raw=raw)
    text = raw.strip().casefold().rstrip(".")
    text = re.sub(r"^(?:by|до|к)\s+", "", text)
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return Due(raw=raw, date=date.fromisoformat(text), resolution="explicit")
        if re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4}", text):
            day, month, year = map(int, text.split("."))
            return Due(raw=raw, date=date(year, month, day), resolution="explicit")
        # Full dates only: never supply an omitted year from today's clock.
        match = re.fullmatch(r"([a-z]+) (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})", text)
        if match and match[1] in MONTHS:
            return Due(
                raw=raw,
                date=date(int(match[3]), MONTHS[match[1]], int(match[2])),
                resolution="explicit",
            )
        match = re.fullmatch(r"(\d{1,2}) (\w+) (\d{4})(?: года| г)?", text)
        if match and match[2] in MONTHS:
            return Due(
                raw=raw,
                date=date(int(match[3]), MONTHS[match[2]], int(match[1])),
                resolution="explicit",
            )
        match = re.fullmatch(r"(\d{4}) жылғы (\d{1,2}) (\w+)", text)
        if match and match[3] in MONTHS:
            return Due(
                raw=raw,
                date=date(int(match[1]), MONTHS[match[3]], int(match[2])),
                resolution="explicit",
            )
    except ValueError:
        return Due(raw=raw, resolution="ambiguous")
    offset = OFFSETS.get(text)
    if offset is None:
        for pattern in (
            r"in (\d{1,3}) days?",
            r"через (\d{1,3}) (?:день|дня|дней)",
            r"(\d{1,3}) күннен кейін",
        ):
            match = re.fullmatch(pattern, text)
            if match:
                offset = int(match[1])
                break
    if offset is None:
        return Due(raw=raw, resolution="ambiguous")
    if meeting_date is None:
        return Due(raw=raw, resolution="needs_meeting_date")
    try:
        return Due(raw=raw, date=meeting_date + timedelta(days=offset), resolution="relative")
    except OverflowError:
        return Due(raw=raw, resolution="ambiguous")
