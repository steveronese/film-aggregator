"""Manual screening entries for venues that can't be auto-scraped (e.g. Cinema Godard, museums).

Read from scrapers/manual_screenings.yaml; entries are merged into the RawScreening stream
by run.py before matching. This is the way to keep WAF-blocked or irregularly-scheduled venues
(like Fondazione Prada's Cinema Godard) live without needing headless Chromium on the cloud cron.

To add a screening: edit manual_screenings.yaml on GitHub.com (no terminal needed) or locally,
commit/push, and the next build includes it.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

from ..base import BaseScraper
from ..models import Language, RawScreening

MANUAL_PATH = Path(__file__).parent.parent / "manual_screenings.yaml"


class ManualScraper(BaseScraper):
    """Reads manual_screenings.yaml and yields its entries as RawScreening."""

    def __init__(self, client=None):
        # Override to skip cinema_id check (entries specify their own).
        self.client = client

    def fetch(self) -> list[RawScreening]:
        if not MANUAL_PATH.exists():
            return []
        data = yaml.safe_load(MANUAL_PATH.read_text(encoding="utf-8")) or {}
        screenings: list[RawScreening] = []
        for entry in data.get("screenings") or []:
            try:
                start = datetime.fromisoformat(entry["start"])
                lang = Language(entry.get("language", "unknown"))
            except (KeyError, ValueError) as e:
                continue  # skip malformed entries
            screenings.append(
                RawScreening(
                    cinema_id=entry["cinema_id"],
                    raw_title=entry["raw_title"],
                    start=start,
                    language=lang,
                    source_url=str(MANUAL_PATH),
                )
            )
        return screenings
