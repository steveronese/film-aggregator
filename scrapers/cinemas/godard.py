"""Scraper for Cinema Godard (Fondazione Prada).

Fondazione Prada's site and ticketing sit behind a WAF that returns 403 to non-browser requests,
so we render the ticketing programme in a headless browser (see scrapers/headless.py). The
programme is a grid of event cards, each reading "Milano | <DD Mon> | <FILM TITLE> | <HH:MM> |
<section>".
"""

from __future__ import annotations

import logging
import os

from bs4 import BeautifulSoup

from ..base import BaseScraper
from ..dates import combine, parse_italian_date, parse_time
from ..models import Language, RawScreening

TICKETING_URL = "https://ticketing.fondazioneprada.org/ticketing/UIPublic/CinemaHome.aspx"

log = logging.getLogger(__name__)


class GodardScraper(BaseScraper):
    cinema_id = "godard"
    # Cinema Godard curates international cinema, screened in original language with subtitles.
    default_language = Language.ORIGINAL_SUBBED

    def fetch(self) -> list[RawScreening]:
        # Fondazione Prada's WAF blocks datacenter IPs and no free aggregator carries Godard's
        # showtimes, so we fetch the real ticketing page one of two ways:
        #  - locally (ENABLE_HEADLESS): a real headless browser on a residential IP;
        #  - in the cloud (SCRAPERAPI_KEY): via ScraperAPI, which renders JS through residential IPs.
        # With neither, we skip and run.py preserves Godard's last-known-good screenings.
        html = self._fetch_html()
        if html is None:
            return []
        return self._parse(BeautifulSoup(html, "html.parser"))

    def _fetch_html(self) -> str | None:
        if os.environ.get("ENABLE_HEADLESS"):
            from ..headless import render_html
            return render_html(TICKETING_URL, wait_ms=4000)
        key = os.environ.get("SCRAPERAPI_KEY")
        if key:
            import httpx
            try:
                # premium proxies + JS render to clear Fondazione Prada's Cloudflare.
                r = httpx.get("https://api.scraperapi.com/", timeout=120, params={
                    "api_key": key, "url": TICKETING_URL, "render": "true",
                    "premium": "true", "country_code": "it"})
                r.raise_for_status()
                return r.text
            except httpx.HTTPError as e:
                log.warning("godard: ScraperAPI fetch failed: %s", e)
                return None
        log.info("godard: no ENABLE_HEADLESS or SCRAPERAPI_KEY — skipping (preserved from prior run)")
        return None

    def _parse(self, soup: BeautifulSoup) -> list[RawScreening]:
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
