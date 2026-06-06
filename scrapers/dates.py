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


def _month_num(token: str) -> int | None:
    """Italian month name or abbreviation (e.g. 'giugno' or 'Giu') → 1-12."""
    t = token.lower()
    if t in IT_MONTHS:
        return IT_MONTHS[t]
    # 3-letter prefixes are unique among Italian months ("giu", "mag", "mar", ...).
    return next((num for name, num in IT_MONTHS.items() if name.startswith(t[:3])), None)


def parse_italian_date(text: str, today: date | None = None) -> date | None:
    """Parse the first 'DD <month>' in text (e.g. 'sabato 06 Giugno', '06 Giu') → date.
    Infers the omitted year by choosing the soonest plausible occurrence on/after yesterday."""
    today = today or date.today()
    for m in _DAY_MONTH.finditer(text):  # scan past false matches (e.g. a time's minutes)
        month = _month_num(m.group(2))
        if not month:
            continue
        day = int(m.group(1))
        for year in (today.year, today.year + 1, today.year - 1):
            try:
                cand = date(year, month, day)
            except ValueError:
                continue
            if cand >= today - timedelta(days=1):
                return cand
    return None


_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def parse_dmy(text: str) -> date | None:
    """Parse a 'DD/MM/YYYY' date (the format 18tickets uses)."""
    m = _DMY.search(text)
    if not m:
        return None
    d, mo, y = (int(g) for g in m.groups())
    try:
        return date(y, mo, d)
    except ValueError:
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
