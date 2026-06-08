"""Registry of active cinema scrapers.

Add a cinema by implementing a BaseScraper subclass in its own module here and appending its
class to SCRAPERS. The orchestrator (scrapers.run) instantiates and runs each one.
"""

from __future__ import annotations

from ..base import BaseScraper
from .bandhi import BeltradeScraper
from .cineteca import CinetecaScraper
from .godard import GodardScraper
from .manual import ManualScraper
from .mymovies import mymovies_scrapers
from .webtic import webtic_scrapers
from .eighteentickets import (
    AnteoScraper,
    AriAnteoFabbricaDelVaporeScraper,
    AriAnteoIncoronataScraper,
    AriAnteoPalazzoRealeScraper,
    AriAnteoVillaRealeScraper,
    AriostoScraper,
    CityLifeAnteoScraper,
    IlCineminoScraper,
)

SCRAPERS: list[type[BaseScraper]] = [
    BeltradeScraper,
    CinetecaScraper,
    AnteoScraper,
    AriostoScraper,
    CityLifeAnteoScraper,
    IlCineminoScraper,
    GodardScraper,  # headless (Playwright) — Fondazione Prada
    ManualScraper,  # manual entries from manual_screenings.yaml (Cinema Godard, museums, ...)
    # Seasonal open-air (empty off-season):
    AriAnteoIncoronataScraper,
    AriAnteoPalazzoRealeScraper,
    AriAnteoVillaRealeScraper,
    AriAnteoFabbricaDelVaporeScraper,
    # Webtic venues (Arcobaleno, Ducale, Plinius, Orfeo, Colosseo, Eliseo, Centrale, San Fedele,
    # Notorious Gloria, UCI Bicocca, Cinelandia Certosa) — pre-configured instances:
    *webtic_scrapers(),
    # mymovies fallback (today-only) for gap venues: Mexico, Gregorianum, Notorious Merlata Bloom:
    *mymovies_scrapers(),
]
