"""Scraper for Cinema Godard (Fondazione Prada).

Fondazione Prada's site and ticketing sit behind a WAF that returns 403 to non-browser requests,
so we render the ticketing programme in a headless browser (see scrapers/headless.py). The
programme is a grid of event cards, each reading "Milano | <DD Mon> | <FILM TITLE> | <HH:MM> |
<section>".
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..base import BaseScraper
from ..dates import combine, parse_italian_date, parse_time
from ..headless import render_html
from ..models import Language, RawScreening

TICKETING_URL = "https://ticketing.fondazioneprada.org/ticketing/UIPublic/CinemaHome.aspx"


class GodardScraper(BaseScraper):
    cinema_id = "godard"
    # Cinema Godard curates international cinema, screened in original language with subtitles.
    default_language = Language.ORIGINAL_SUBBED

    def fetch(self) -> list[RawScreening]:
        soup = BeautifulSoup(render_html(TICKETING_URL, wait_ms=4000), "html.parser")
        screenings: list[RawScreening] = []
        seen: set[tuple[str, str]] = set()

        for card in soup.select(".col-xs-6.col-sm-4.col-md-3"):
            # Card layout: location · date(.block-title) · TITLE(.related-event-date[0]) · time · section
            rel = card.select(".related-event-date")
            title = rel[0].get_text(" ", strip=True) if rel else None
            text = " ".join(card.stripped_strings)
            day = parse_italian_date(text)
            start_time = parse_time(text)
            if not title or day is None or start_time is None:
                continue
            start = combine(day, start_time)
            key = (title, start.isoformat())
            if key in seen:
                continue
            seen.add(key)
            screenings.append(
                RawScreening(
                    cinema_id=self.cinema_id,
                    raw_title=title,
                    start=start,
                    language=self.default_language,
                    source_url=TICKETING_URL,
                )
            )
        return screenings
