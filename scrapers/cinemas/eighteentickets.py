"""Scraper for cinemas selling tickets through the 18tickets.it platform.

18tickets is a white-label ticketing service used by many Italian cinemas (Anteo, Cineteca, ...),
each on its own `<sub>.18tickets.it` subdomain. It has no robots.txt restrictions and renders the
schedule server-side, making it a clean, permitted source — notably for Anteo, whose own site
(spaziocinema.info) disallows crawling its programme.

The cinema landing page carries the full date window: per-film blocks (`.schedule-section-show`)
with date headers (`.time-select__place`, "Domenica 07/06/2026 …") and showtime links
("HH:MM <screen>"). The only thing missing there is the film title, so we resolve each film id to
its title from `/film/<id>` (`<title>`), cached persistently so we fetch each id only once.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from ..base import BaseScraper
from ..dates import combine, parse_dmy, parse_time
from ..models import Language, RawScreening

TITLE_CACHE = Path(__file__).parent.parent / "cache" / "18tickets_titles.json"
_FILM_ID = re.compile(r"/film/(\d+)")
# Anteo (and others) prefix original-language screenings in the title, e.g.
# "V.O. SOTT. ITA - DISCLOSURE DAY" or "V.O. SOTT ENG - ROJO CLAVEL".
_VO_MARKER = re.compile(r"\bv\.\s*o\b|\bv\.o\.|versione\s+originale|\bsott", re.IGNORECASE)


def detect_language(title: str, default: Language) -> Language:
    return Language.ORIGINAL_SUBBED if _VO_MARKER.search(title) else default


class EighteenTicketsScraper(BaseScraper):
    """Generic 18tickets cinema. Subclasses set `cinema_id` and `subdomain`."""

    subdomain: str = ""  # e.g. "anteo.spaziocinema"
    default_language: Language = Language.UNKNOWN
    # "landing": the homepage carries the full dated schedule (Anteo theme).
    # "filmpages": homepage only lists films; dates/times live on each /film/<id> (Cinemino theme).
    mode: str = "landing"

    def __init__(self, client=None) -> None:
        super().__init__(client)
        self._titles: dict[str, str] = self._load_titles()
        self._titles_dirty = False

    @property
    def base_url(self) -> str:
        return f"https://{self.subdomain}.18tickets.it"

    @staticmethod
    def _load_titles() -> dict[str, str]:
        if TITLE_CACHE.exists():
            return json.loads(TITLE_CACHE.read_text(encoding="utf-8"))
        return {}

    def _save_titles(self) -> None:
        if not self._titles_dirty:
            return
        TITLE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        TITLE_CACHE.write_text(
            json.dumps(self._titles, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )

    def title_for(self, film_id: str) -> str | None:
        key = f"{self.subdomain}:{film_id}"
        if key in self._titles:
            return self._titles[key] or None
        try:
            from bs4 import BeautifulSoup

            html = self.get(f"{self.base_url}/film/{film_id}").text
            title = BeautifulSoup(html, "html.parser").title
            value = title.get_text(strip=True) if title else ""
        except Exception:  # noqa: BLE001 - a missing title shouldn't sink the run
            value = ""
        self._titles[key] = value
        self._titles_dirty = True
        return value or None

    def fetch(self) -> list[RawScreening]:
        if not self.subdomain:
            raise ValueError(f"{type(self).__name__} must set subdomain")
        from bs4 import BeautifulSoup

        landing = BeautifulSoup(self.get(f"{self.base_url}/").text, "html.parser")
        screenings: list[RawScreening] = []
        seen: set[tuple] = set()

        if self.mode == "landing":
            for block in landing.select(".schedule-section-show"):
                link = block.select_one('a[href*="/film/"]')
                m = _FILM_ID.search(link.get("href") or "") if link else None
                if not m:
                    continue
                title = self.title_for(m.group(1))
                if title:
                    self._parse_block(block, title, seen, screenings)
        else:  # filmpages: homepage lists films; each /film/<id> holds the dated schedule
            film_ids: list[str] = []
            for a in landing.select('a[href*="/film/"]'):
                m = _FILM_ID.search(a.get("href") or "")
                if m and m.group(1) not in film_ids:
                    film_ids.append(m.group(1))
            for fid in film_ids:
                try:
                    fsoup = BeautifulSoup(self.get(f"{self.base_url}/film/{fid}").text, "html.parser")
                except Exception:  # noqa: BLE001 - one broken film page shouldn't sink the run
                    continue
                title = fsoup.title.get_text(strip=True) if fsoup.title else None
                if not title:
                    continue
                for block in fsoup.select(".schedule-section-show"):
                    self._parse_block(block, title, seen, screenings)

        self._save_titles()
        return screenings

    def _parse_block(self, block, title: str, seen: set, screenings: list) -> None:
        """Walk one .schedule-section-show, tracking the current date header and emitting a
        screening per showtime. Times are either a-links ("HH:MM <screen>", landing theme) or
        `.time-select__item` buttons ("<screen> HH:MM", film-page theme)."""
        has_items = block.select_one(".time-select__item") is not None

        def is_node(t) -> bool:
            cls = t.get("class") or []
            if "time-select__place" in cls:
                return True
            if has_items:
                return "time-select__item" in cls
            return t.name == "a" and "/film/" in (t.get("href") or "")

        current_date: date | None = None
        for el in block.find_all(is_node):
            if "time-select__place" in (el.get("class") or []):
                current_date = parse_dmy(el.get_text(" ", strip=True))
                continue
            if current_date is None:
                continue
            txt = el.get_text(" ", strip=True)
            t = parse_time(txt)
            if t is None:
                continue
            hall = re.sub(r"\d{1,2}[:.]\d{2}", "", txt).strip(" -·") or None
            booking = el.get("href") if el.name == "a" else (
                el.find("a").get("href") if el.find("a") else None
            )
            dedup = (title, current_date.isoformat(), str(t), hall or "")
            if dedup in seen:
                continue
            seen.add(dedup)
            screenings.append(
                RawScreening(
                    cinema_id=self.cinema_id,
                    raw_title=title,
                    start=combine(current_date, t),
                    hall=hall,
                    language=detect_language(title, self.default_language),
                    booking_url=booking or f"{self.base_url}/",
                    source_url=f"{self.base_url}/",
                )
            )


class AnteoScraper(EighteenTicketsScraper):
    cinema_id = "anteo"
    subdomain = "anteo.spaziocinema"


class IlCineminoScraper(EighteenTicketsScraper):
    cinema_id = "cinemino"
    subdomain = "ilcinemino.ilcinemino"
    mode = "filmpages"  # homepage is a carousel; schedule is on each film page


class AriostoScraper(EighteenTicketsScraper):
    cinema_id = "ariosto"
    subdomain = "ariosto.spaziocinema"


class CityLifeAnteoScraper(EighteenTicketsScraper):
    cinema_id = "citylife-anteo"
    subdomain = "citylife.spaziocinema"


# Seasonal AriAnteo open-air venues (summer); empty off-season, which is harmless.
class AriAnteoIncoronataScraper(EighteenTicketsScraper):
    cinema_id = "arianteo-incoronata"
    subdomain = "incoronata.spaziocinema"


class AriAnteoPalazzoRealeScraper(EighteenTicketsScraper):
    cinema_id = "arianteo-palazzoreale"
    subdomain = "palazzoreale.spaziocinema"


class AriAnteoVillaRealeScraper(EighteenTicketsScraper):
    cinema_id = "arianteo-villareale"
    subdomain = "villareale.spaziocinema"


class AriAnteoFabbricaDelVaporeScraper(EighteenTicketsScraper):
    cinema_id = "arianteo-fabbricadelvapore"
    subdomain = "fabbricadelvapore.spaziocinema"
