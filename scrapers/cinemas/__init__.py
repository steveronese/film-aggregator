"""Registry of active cinema scrapers.

Add a cinema by implementing a BaseScraper subclass in its own module here and appending its
class to SCRAPERS. The orchestrator (scrapers.run) instantiates and runs each one.
"""

from __future__ import annotations

from ..base import BaseScraper
from .stub import StubScraper

# Real per-cinema scrapers get added here in Phase 2 (beltrade, cineteca, mexico, ...).
SCRAPERS: list[type[BaseScraper]] = [
    StubScraper,
]
