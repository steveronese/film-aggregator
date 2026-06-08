"""Scraper for venues only reachable through the mymovies.it aggregator.

Used as a fallback for Milan cinemas we can't scrape directly (no own ticketing platform we
support): Cinema Mexico, Gregorianum, Notorious Merlata Bloom. mymovies is server-rendered (no JS
needed) but only exposes the CURRENT DAY's showtimes per cinema, so coverage is one day deep —
acceptable for these gap venues. Each film block is a title followed by an `.orari-dettaglio`
list of times.
"""

from __future__ import annotations

import re
from datetime import datetime

from ..base import BaseScraper
from ..dates import parse_time
from ..models import Language, RawScreening

_VO = re.compile(r"\bv\.\s*o\b|versione\s+originale|sottotitol", re.IGNORECASE)


class MyMoviesScraper(BaseScraper):
    """One Milan cinema on mymovies.it, by its numeric id."""

    def __init__(self, cinema_id: str, mymovies_id: int, default_language: Language = Language.UNKNOWN,
                 client=None) -> None:
        self.cinema_id = cinema_id
        self.mymovies_id = mymovies_id
        self.default_language = default_language
        super().__init__(client)

    def fetch(self) -> list[RawScreening]:
        from bs4 import BeautifulSoup

        url = f"https://www.mymovies.it/cinema/milano/{self.mymovies_id}/"
        soup = BeautifulSoup(self.get(url).text, "html.parser")
        today = datetime.now().date()
        screenings: list[RawScreening] = []
        seen: set[tuple[str, str]] = set()

        for orari in soup.select(".orari-dettaglio"):
            times = re.findall(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b", orari.get_text(" ", strip=True))
            if not times:
                continue
            title_el = orari.find_previous(class_=re.compile("titolo"))
            title = title_el.get_text(" ", strip=True) if title_el else None
            if not title or len(title) < 2:
                continue
            language = Language.ORIGINAL_SUBBED if _VO.search(title) else self.default_language
            for hh, mm in times:
                t = parse_time(f"{hh}:{mm}")
                if t is None:
                    continue
                start = datetime.combine(today, t)
                key = (title, start.isoformat())
                if key in seen:
                    continue
                seen.add(key)
                screenings.append(
                    RawScreening(
                        cinema_id=self.cinema_id,
                        raw_title=title,
                        start=start,
                        language=language,
                        booking_url=url,
                        source_url=url,
                    )
                )
        return screenings


# (cinema_id, mymovies numeric id, default language) — gap venues we can't scrape directly.
MYMOVIES_VENUES: list[tuple[str, int, Language]] = [
    ("mexico", 5546, Language.UNKNOWN),
    ("gregorianum", 6483, Language.UNKNOWN),
    ("notorious-merlata", 24450, Language.UNKNOWN),
]


def mymovies_scrapers() -> list[MyMoviesScraper]:
    return [MyMoviesScraper(cid, mid, lang) for cid, mid, lang in MYMOVIES_VENUES]
