"""Scraper for Cineteca Milano (cinetecamilano.it) — venues Arlecchino, MIC, Metropolis.

The public calendar is rendered client-side by the site's bespoke `cinetecamilano-calendar`
plugin, which POSTs to admin-ajax.php (action `dkrcmc_ajax_filter`) and gets back structured JSON
per day. We replicate that request: fetch /calendario/ once for a fresh nonce and the filter
definitions, then query each upcoming day. The JSON is rich — it carries the venue and an explicit
language label, so VO vs dubbed is known directly rather than guessed.
"""

from __future__ import annotations

import datetime
import json
import re
from urllib.parse import urlencode

from ..base import BaseScraper
from ..dates import combine, parse_time
from ..models import Language, RawScreening

CALENDAR_URL = "https://www.cinetecamilano.it/calendario/"
AJAX_URL = "https://www.cinetecamilano.it/wp-admin/admin-ajax.php"
DAYS_AHEAD = 14

_NONCE_RE = re.compile(r'"dkrcmc_ajax_nonce":"([a-z0-9]+)"')


def place_to_cinema_id(place: str) -> str:
    p = place.lower()
    if "arlecchino" in p:
        return "cineteca-arlecchino"
    if "mic" in p:
        return "cineteca-mic"
    if "metropolis" in p:
        return "cineteca-metropolis"
    if "oberdan" in p:
        return "cineteca-oberdan"
    # Fallback for any venue we haven't registered yet (orchestrator will warn).
    tail = re.sub(r"^cineteca\s+milano\s+", "", p).strip()
    return "cineteca-" + (re.sub(r"[^a-z0-9]+", "-", tail).strip("-") or "altro")


def map_language(label: str) -> Language:
    s = (label or "").lower()
    if "originale" in s:
        return Language.ORIGINAL_SUBBED if "sottotitol" in s else Language.ORIGINAL
    if "italiano" in s:
        return Language.DUBBED
    return Language.UNKNOWN


class CinetecaScraper(BaseScraper):
    cinema_id = "cineteca"  # logical group; per-screening cinema_id is resolved from `place`.
    days_ahead = DAYS_AHEAD

    def fetch(self) -> list[RawScreening]:
        html = self.get(CALENDAR_URL).text
        m = _NONCE_RE.search(html)
        if not m:
            raise RuntimeError("Could not find dkrcmc ajax nonce on the calendar page")
        nonce = m.group(1)
        filters, transient_suffix = self._parse_filters(html)

        seen: set[tuple[str, str, str]] = set()
        screenings: list[RawScreening] = []
        today = datetime.date.today()
        for offset in range(self.days_ahead):
            day = today + datetime.timedelta(days=offset)
            for item in self._query_day(day, nonce, filters, transient_suffix):
                rs = self._to_screening(item)
                if rs is None:
                    continue
                key = (rs.cinema_id, rs.raw_title, rs.start.isoformat())
                if key in seen:
                    continue
                seen.add(key)
                screenings.append(rs)
        return screenings

    @staticmethod
    def _parse_filters(html: str) -> tuple[list[str], str]:
        """Return (filter JSON strings, concatenated checkbox transient suffix)."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        filters: list[str] = []
        suffix = ""
        for cb in soup.select(".dkrcmc-filter-checkbox"):
            value = cb.get("value")
            if not value:
                continue
            try:
                filters.append(json.dumps(json.loads(value)))
            except json.JSONDecodeError:
                continue
            suffix += cb.get("data-transient") or ""
        return filters, suffix

    @staticmethod
    def _date_transient(day: datetime.date) -> str:
        # Replicate the plugin's JS: first 10 chars of new Date("YYYY-MM-DD").getTime().
        ts = datetime.datetime(day.year, day.month, day.day, tzinfo=datetime.timezone.utc).timestamp()
        return str(int(ts))

    def _query_day(self, day, nonce, filters, transient_suffix):
        date_str = day.isoformat()
        transient = self._date_transient(day) + transient_suffix
        passed = [json.dumps({"dkrcmc_date": date_str})] + filters + [json.dumps({"dkrcmc_transient": transient})]
        form = [("action", "dkrcmc_ajax_filter"), ("dkrcmc_ajax_nonce", nonce)]
        form += [("dkrcmc_passed_values[]", v) for v in passed]
        resp = self.post(
            AJAX_URL,
            content=urlencode(form),
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        try:
            parsed = json.loads(resp.text)
        except json.JSONDecodeError:
            return []
        if parsed.get("error"):
            return []
        data = parsed.get("dkrcmc-data") or {}
        return list(data.values()) if isinstance(data, dict) else data

    def _to_screening(self, item: dict) -> RawScreening | None:
        # Keep only single-occurrence dated screenings; skip ongoing exhibitions (date ranges).
        if item.get("end"):
            return None
        start_date = item.get("start")
        start_time = parse_time(item.get("date") or "")
        if not start_date or start_time is None:
            return None
        try:
            day = datetime.date.fromisoformat(start_date)
        except ValueError:
            return None
        title = (item.get("title") or "").strip()
        if not title:
            return None
        return RawScreening(
            cinema_id=place_to_cinema_id(item.get("place") or ""),
            raw_title=title,
            start=combine(day, start_time),
            language=map_language(item.get("language") or ""),
            booking_url=item.get("ticket") or None,
            source_url=CALENDAR_URL,
        )
