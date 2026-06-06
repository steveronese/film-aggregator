"""Match a messy, Italian, sometimes-retrospective screening title to a canonical TMDB film.

This is the technical heart of the project. Niche and restored films are exactly the cases
automated matching gets wrong, so manual overrides always win and anything unmatched is reported
for triage into overrides.yaml.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path

import yaml
from rapidfuzz import fuzz

from .models import Film
from .tmdb import TMDBClient

log = logging.getLogger(__name__)

OVERRIDES_PATH = Path(__file__).parent / "overrides.yaml"

# Accept a fuzzy match only at/above this score (0-100).
MATCH_THRESHOLD = 85

# Noise commonly appended to Italian listings that should not affect matching.
_NOISE = re.compile(
    r"\b(v\.?\s*o\.?\s*(sott\.?\s*)?(it(a(liano)?)?|eng|ing(lese)?)?|"
    r"versione\s+originale(\s+sottotitolata)?|"
    r"sott(\.|otitol\w*)?\s*(it(a(liano)?)?|eng|ing(lese)?)?|"
    r"sub\.?\s*ita(liano)?|original\s+version|o\.?v\.?|in\s+lingua\s+originale|"
    r"\d{4}\s*restaurato|restaurato|edizione\s+restaurata|replica|"
    r"(orario|data)\s+da\s+(definire|confermare)|posti\s+esauriti|sold\s*out|anteprima)\b",
    re.IGNORECASE,
)


def normalize_title(title: str) -> str:
    """Lowercase, strip accents and listing noise, drop trailing year, collapse punctuation."""
    text = unicodedata.normalize("NFKD", title)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = _NOISE.sub(" ", text)
    text = re.sub(r"[\(\[]\s*\d{4}\s*[\)\]]", " ", text)  # "(2023)"
    text = re.sub(r"\b(19|20)\d{2}\b", " ", text)          # bare year
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _year_of(details: dict) -> int | None:
    date = details.get("release_date") or ""
    return int(date[:4]) if len(date) >= 4 and date[:4].isdigit() else None


def _director_of(details: dict) -> str | None:
    crew = (details.get("credits") or {}).get("crew") or []
    directors = [c["name"] for c in crew if c.get("job") == "Director"]
    return ", ".join(directors) or None


def _film_from_details(details: dict) -> Film:
    return Film(
        tmdb_id=details["id"],
        title=details.get("title") or details.get("original_title") or "",
        original_title=details.get("original_title"),
        italian_title=details.get("title"),
        year=_year_of(details),
        poster_path=details.get("poster_path"),
        overview=details.get("overview") or None,
        runtime=details.get("runtime") or None,
        director=_director_of(details),
        genres=[g["name"] for g in (details.get("genres") or [])],
    )


class FilmMatcher:
    def __init__(self, tmdb: TMDBClient, overrides_path: Path = OVERRIDES_PATH) -> None:
        self.tmdb = tmdb
        self.overrides = self._load_overrides(overrides_path)
        self._cache: dict[tuple[str, int | None], Film | None] = {}

    @staticmethod
    def _load_overrides(path: Path) -> dict[str, int]:
        if not path.exists():
            return {}
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        # Keys are matched on their normalized form so listing noise is irrelevant.
        return {normalize_title(str(k)): int(v) for k, v in raw.items()}

    def match(self, raw_title: str, year: int | None = None) -> Film | None:
        norm = normalize_title(raw_title)
        if not norm:
            return None
        cache_key = (norm, year)
        if cache_key in self._cache:
            return self._cache[cache_key]

        film = self._match_uncached(raw_title, norm, year)
        self._cache[cache_key] = film
        return film

    def _match_uncached(self, raw_title: str, norm: str, year: int | None) -> Film | None:
        # 1. Manual override always wins.
        if norm in self.overrides:
            details = self.tmdb.movie_details(self.overrides[norm])
            if details:
                return _film_from_details(details)
            log.warning("Override for %r -> %s but no details available", raw_title, self.overrides[norm])
            return None

        # 2. Fuzzy search against TMDB.
        candidates = self.tmdb.search_movie(norm, year)
        best_id, best_score = None, 0.0
        for cand in candidates:
            for field in ("title", "original_title"):
                value = cand.get(field)
                if not value:
                    continue
                score = fuzz.token_sort_ratio(norm, normalize_title(value))
                if score > best_score:
                    best_score, best_id = score, cand["id"]

        if best_id is not None and best_score >= MATCH_THRESHOLD:
            details = self.tmdb.movie_details(best_id)
            if details:
                return _film_from_details(details)
        return None
