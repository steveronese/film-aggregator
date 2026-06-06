"""Parsing helpers for the Italian date/time strings cinema sites use."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

IT_MONTHS = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}

_DAY_MONTH = re.compile(r"(\d{1,2})\s+([A-Za-zàèéìòù]+)", re.IGNORECASE)
_TIME = re.compile(r"(\d{1,2})[:.](\d{2})")


def parse_italian_date(text: str, today: date | None = None) -> date | None:
    """Parse a header like 'OGGI, sabato 06 Giugno' → date. Infers the year (headers omit it)
    by choosing the soonest plausible occurrence on/after yesterday."""
    today = today or date.today()
    m = _DAY_MONTH.search(text)
    if not m:
        return None
    day = int(m.group(1))
    month = IT_MONTHS.get(m.group(2).lower())
    if not month:
        return None
    for year in (today.year, today.year + 1, today.year - 1):
        try:
            cand = date(year, month, day)
        except ValueError:
            continue
        if cand >= today - timedelta(days=1):
            return cand
    return None


def parse_time(text: str) -> time | None:
    """Parse 'ORE 19:40' / '19.40' → time."""
    m = _TIME.search(text)
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)


def combine(d: date, t: time) -> datetime:
    return datetime.combine(d, t)
