"""Scraper for arthouse cinemas hosted on bandhi.it.

bandhi.it is a shared WordPress + "WP Theatre" platform used by several Milan arthouse cinemas
(Beltrade among them). The schedule is rendered server-side as a WP Theatre listing: date-group
headers (`.wpt_listing_group`, e.g. "OGGI, sabato 06 Giugno") followed by event rows
(`.wp_theatre_event`) carrying a title and a start time. The event-date post meta isn't exposed
over the REST API, so we parse the rendered listing — but one scraper covers every bandhi cinema.
"""

from __future__ import annotations

from datetime import date

from bs4 import BeautifulSoup

from ..base import BaseScraper
from ..dates import combine, parse_italian_date, parse_time
from ..models import Language, RawScreening


def _has_token(tag, token: str) -> bool:
    return tag.has_attr("class") and token in tag["class"]


class BandhiScraper(BaseScraper):
    """Generic bandhi.it cinema. Subclasses set `cinema_id`, `slug`, and `default_language`."""

    slug: str = ""
    default_language: Language = Language.ORIGINAL_SUBBED

    @property
    def url(self) -> str:
        return f"https://bandhi.it/bah/{self.slug}/"

    def fetch(self) -> list[RawScreening]:
        if not self.slug:
            raise ValueError(f"{type(self).__name__} must set slug")
        html = self.get(self.url).text
        return self.parse(html, self.url)

    def parse(self, html: str, source_url: str, today: date | None = None) -> list[RawScreening]:
        soup = BeautifulSoup(html, "html.parser")

        # The page has two listings: the real schedule and a "prossimamente" (coming soon)
        # teaser without dates. Take the first non-prossimamente events listing.
        listing = None
        for li in soup.select(".wpt_listing.wpt_events"):
            if "wpt_prossimamente_list" not in li.get("class", []):
                listing = li
                break
        if listing is None:
            return []

        nodes = listing.find_all(
            lambda t: _has_token(t, "wpt_listing_group") or _has_token(t, "wp_theatre_event")
        )

        screenings: list[RawScreening] = []
        current_date: date | None = None
        for node in nodes:
            if _has_token(node, "wpt_listing_group"):
                current_date = parse_italian_date(node.get_text(" ", strip=True), today)
                continue
            if current_date is None:
                continue
            title_el = node.select_one(".wp_theatre_event_title")
            time_el = node.select_one(".wp_theatre_event_time, .wp_theatre_event_starttime")
            if not title_el or not time_el:
                continue
            start_time = parse_time(time_el.get_text(" ", strip=True))
            if start_time is None:
                continue
            title = title_el.get_text(" ", strip=True)
            if not title:
                continue
            link_el = node.select_one("a[href]")
            href = link_el["href"] if link_el else source_url
            screenings.append(
                RawScreening(
                    cinema_id=self.cinema_id,
                    raw_title=title,
                    start=combine(current_date, start_time),
                    language=self.default_language,
                    booking_url=href,
                    source_url=source_url,
                )
            )
        return screenings


class BeltradeScraper(BandhiScraper):
    cinema_id = "beltrade"
    slug = "beltrade"
    # Beltrade screens everything in original language with Italian subtitles.
    default_language = Language.ORIGINAL_SUBBED
