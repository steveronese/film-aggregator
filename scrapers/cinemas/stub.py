"""A stub scraper that emits fixed sample screenings.

It exercises the whole pipeline offline (no network, no TMDB key) across all three matching paths:
an override match, a fuzzy-search match (seeded in the committed cache), and an unmatched title.
Real scrapers replace this in Phase 2.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ..base import BaseScraper
from ..models import Language, RawScreening


class StubScraper(BaseScraper):
    cinema_id = "beltrade"

    def fetch(self) -> list[RawScreening]:
        base = datetime.now().replace(hour=21, minute=0, second=0, microsecond=0)
        return [
            # 1. Matches via overrides.yaml ("Perfect Days" -> 976893).
            RawScreening(
                cinema_id=self.cinema_id,
                raw_title="Perfect Days (v.o. sub ita)",
                start=base + timedelta(days=1),
                hall="Sala 1",
                language=Language.ORIGINAL_SUBBED,
                source_url="https://www.cinemabeltrade.net/",
            ),
            # 2. Matches via fuzzy search (seeded in cache/tmdb.json).
            RawScreening(
                cinema_id=self.cinema_id,
                raw_title="La Chimera",
                start=base + timedelta(days=2),
                hall="Sala 1",
                language=Language.ORIGINAL,
                source_url="https://www.cinemabeltrade.net/",
            ),
            # 3. Deliberately unmatched -> lands in data/unmatched.json for triage.
            RawScreening(
                cinema_id=self.cinema_id,
                raw_title="Retrospettiva: Un Film Introvabile",
                raw_year=1962,
                start=base + timedelta(days=3),
                language=Language.ORIGINAL,
                source_url="https://www.cinemabeltrade.net/",
            ),
        ]
