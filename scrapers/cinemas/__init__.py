"""Registry of active cinema scrapers.

Add a cinema by implementing a BaseScraper subclass in its own module here and appending its
class to SCRAPERS. The orchestrator (scrapers.run) instantiates and runs each one.
"""

from __future__ import annotations

from ..base import BaseScraper
from .bandhi import BeltradeScraper
from .cineteca import CinetecaScraper

SCRAPERS: list[type[BaseScraper]] = [
    BeltradeScraper,
    CinetecaScraper,
    # Still to add: mexico (site currently down), Anteo circuit (spaziocinema.info), ...
]
