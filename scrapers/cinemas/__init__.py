"""Registry of active cinema scrapers.

Add a cinema by implementing a BaseScraper subclass in its own module here and appending its
class to SCRAPERS. The orchestrator (scrapers.run) instantiates and runs each one.
"""

from __future__ import annotations

from ..base import BaseScraper
from .bandhi import BeltradeScraper

SCRAPERS: list[type[BaseScraper]] = [
    BeltradeScraper,
    # More venues added in Phase 2/5: cineteca (WordPress), mexico (site currently down), ...
]
