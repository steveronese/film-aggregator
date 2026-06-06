"""Scraper for cinemas on the Webtic platform (Crea Informatica).

Webtic's web app is a JS SPA, but it's backed by a clean JSON API we can call directly:
POST secure.webtic.it/api/wtjsonservices.ashx?localid=<id>&wtid=getFullScheduling
returns DS.Scheduling.Events[], each with Title/OriginalTitle/Director/Year, an "O.V."
EventProperty for original-version screenings, and Days[].Performances[] carrying the exact
StartTime, hall (ScreenName) and PerformanceId. No headless browser needed.

A single scraper covers the ~14 Milan cinemas on Webtic; instantiate one per venue (cinema_id +
localid) — see scrapers/cinemas/__init__.py.
"""

from __future__ import annotations

import datetime

from ..base import BaseScraper
from ..models import Language, RawScreening

API = "https://secure.webtic.it/api/wtjsonservices.ashx"
_HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://www.webtic.it",
    "Referer": "https://www.webtic.it/",
}


class WebticScraper(BaseScraper):
    """One Webtic venue. Instantiated with its cinema_id and Webtic localid."""

    def __init__(self, cinema_id: str, localid: int, default_language: Language = Language.UNKNOWN,
                 client=None) -> None:
        self.cinema_id = cinema_id
        self.localid = localid
        self.default_language = default_language
        super().__init__(client)

    def fetch(self) -> list[RawScreening]:
        resp = self.post(
            API,
            params={"languageid": "it", "localid": str(self.localid), "trackid": "33",
                    "wtid": "getFullScheduling"},
            json={},
            headers=_HEADERS,
        )
        events = (((resp.json().get("DS") or {}).get("Scheduling") or {}).get("Events")) or []
        screenings: list[RawScreening] = []
        for ev in events:
            title = ev.get("Title") or ev.get("OriginalTitle")
            if not title:
                continue
            props = {(p.get("EventProperty") or "").upper() for p in (ev.get("EventProperties") or [])}
            is_vo = "O.V." in props or "(o.v.)" in title.lower()
            language = Language.ORIGINAL_SUBBED if is_vo else self.default_language
            for day in ev.get("Days") or []:
                for perf in day.get("Performances") or []:
                    start_raw = perf.get("StartTime")
                    if not start_raw:
                        continue
                    try:
                        start = datetime.datetime.fromisoformat(start_raw)
                    except ValueError:
                        continue
                    screenings.append(
                        RawScreening(
                            cinema_id=self.cinema_id,
                            raw_title=title,
                            start=start,
                            hall=perf.get("ScreenName") or perf.get("Screen"),
                            language=language,
                            booking_url=f"https://www.webtic.it/#/shopping?action=loadLocal&localId={self.localid}",
                            source_url=f"https://www.webtic.it/#/shopping?action=loadLocal&localId={self.localid}",
                        )
                    )
        return screenings


# (cinema_id, Webtic localid, default language). Niche/arthouse/cultural first, then multiplexes.
WEBTIC_VENUES: list[tuple[str, int, Language]] = [
    ("arcobaleno", 5066, Language.UNKNOWN),
    ("ducale", 5065, Language.UNKNOWN),
    ("plinius", 5094, Language.UNKNOWN),
    ("orfeo", 5351, Language.UNKNOWN),
    ("colosseo", 5062, Language.UNKNOWN),
    ("eliseo", 5064, Language.UNKNOWN),
    ("centrale", 5742, Language.UNKNOWN),
    ("san-fedele", 5213, Language.ORIGINAL_SUBBED),  # cultural foundation, arthouse/VO
    ("notorious-gloria", 5491, Language.UNKNOWN),
    ("uci-bicocca", 5068, Language.UNKNOWN),
    ("cinelandia-certosa", 5868, Language.UNKNOWN),
]


def webtic_scrapers() -> list[WebticScraper]:
    return [WebticScraper(cid, lid, lang) for cid, lid, lang in WEBTIC_VENUES]
