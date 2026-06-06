"""Orchestrator: scrape every registered cinema, match titles to TMDB, write data/*.json.

Run with:  python -m scrapers.run
"""

from __future__ import annotations

import json
import logging
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

import yaml

from .cinemas import SCRAPERS
from .matching import FilmMatcher
from .models import Cinema, Film, RawScreening, Screening, UnmatchedTitle
from .tmdb import TMDBClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("scrapers.run")

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CINEMAS_YAML = Path(__file__).parent / "cinemas.yaml"


def load_cinemas() -> list[Cinema]:
    raw = yaml.safe_load(CINEMAS_YAML.read_text(encoding="utf-8")) or []
    return [Cinema(**c) for c in raw]


def collect_raw() -> list[RawScreening]:
    raw: list[RawScreening] = []
    for scraper_cls in SCRAPERS:
        raw.extend(scraper_cls().fetch_safe())
    return raw


def is_upcoming(s: RawScreening, now: datetime) -> bool:
    return s.start >= now


def build(raw_screenings: list[RawScreening], matcher: FilmMatcher):
    """Resolve raw screenings to TMDB films. Returns (screenings, films, unmatched)."""
    films: dict[int, Film] = {}
    unmatched: "OrderedDict[tuple[str, int | None, str], UnmatchedTitle]" = OrderedDict()
    screenings: list[Screening] = []

    for rs in raw_screenings:
        film = matcher.match(rs.raw_title, rs.raw_year)
        tmdb_id = None
        if film is not None:
            tmdb_id = film.tmdb_id
            films[film.tmdb_id] = film
        else:
            key = (rs.raw_title, rs.raw_year, rs.cinema_id)
            if key in unmatched:
                unmatched[key].occurrences += 1
            else:
                unmatched[key] = UnmatchedTitle(
                    raw_title=rs.raw_title, raw_year=rs.raw_year, cinema_id=rs.cinema_id
                )
        screenings.append(
            Screening(
                cinema_id=rs.cinema_id,
                tmdb_id=tmdb_id,
                raw_title=rs.raw_title,
                start=rs.start,
                hall=rs.hall,
                language=rs.language,
                booking_url=rs.booking_url,
                source_url=rs.source_url,
            )
        )

    return screenings, list(films.values()), list(unmatched.values())


def write_json(path: Path, models) -> None:
    path.write_text(
        json.dumps([m.model_dump(mode="json") for m in models], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    now = datetime.now()
    cinemas = load_cinemas()
    valid_ids = {c.id for c in cinemas}

    raw = [s for s in collect_raw() if is_upcoming(s, now)]
    for s in raw:
        if s.cinema_id not in valid_ids:
            log.warning("Screening references unknown cinema_id %r", s.cinema_id)

    tmdb = TMDBClient()
    matcher = FilmMatcher(tmdb)
    screenings, films, unmatched = build(raw, matcher)
    tmdb.save_cache()

    screenings.sort(key=lambda s: (s.start, s.cinema_id))

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    write_json(DATA_DIR / "cinemas.json", cinemas)
    write_json(DATA_DIR / "screenings.json", screenings)
    write_json(DATA_DIR / "films.json", films)
    write_json(DATA_DIR / "unmatched.json", unmatched)

    matched = sum(1 for s in screenings if s.tmdb_id is not None)
    log.info(
        "Wrote %d screenings (%d matched, %d unmatched titles), %d films, %d cinemas.",
        len(screenings), matched, len(unmatched), len(films), len(cinemas),
    )
    if unmatched:
        log.info("Unmatched (triage into overrides.yaml): %s",
                 ", ".join(f"{u.raw_title!r}" for u in unmatched))


if __name__ == "__main__":
    main()
