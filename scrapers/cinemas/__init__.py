"""Registry of active cinema scrapers.

Add a cinema by implementing a BaseScraper subclass in its own module here and appending its
class to SCRAPERS. The orchestrator (scrapers.run) instantiates and runs each one.
"""

from __future__ import annotations

from ..base import BaseScraper
from .bandhi import BeltradeScraper
from .cineteca import CinetecaScraper
from .eighteentickets import (
    AnteoScraper,
    AriAnteoFabbricaDelVaporeScraper,
    AriAnteoIncoronataScraper,
    AriAnteoPalazzoRealeScraper,
    AriAnteoVillaRealeScraper,
    AriostoScraper,
    CityLifeAnteoScraper,
)

SCRAPERS: list[type[BaseScraper]] = [
    BeltradeScraper,
    CinetecaScraper,
    AnteoScraper,
    AriostoScraper,
    CityLifeAnteoScraper,
    # Seasonal open-air (empty off-season):
    AriAnteoIncoronataScraper,
    AriAnteoPalazzoRealeScraper,
    AriAnteoVillaRealeScraper,
    AriAnteoFabbricaDelVaporeScraper,
    # Still to add: Cinenauta (Arcobaleno+Ducale), Il Cinemino, Webtic venues, mexico (down), ...
]
