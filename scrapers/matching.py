"""Match a messy, Italian, sometimes-retrospective screening title to a canonical TMDB film.

This is the technical heart of the project. Niche and restored films are exactly the cases
automated matching gets wrong, so manual overrides always win and anything unmatched is reported
for triage into overrides.yaml.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml
from rapidfuzz import fuzz

from .ai_matcher import AIMatcher
from .models import Film
from .tmdb import TMDBClient

log = logging.getLogger(__name__)

OVERRIDES_PATH = Path(__file__).parent / "overrides.yaml"

# Accept a fuzzy match (with no AI) at/above this score (0-100).
MATCH_THRESHOLD = 85
# At/above this score a fuzzy match is trusted outright (AI not consulted).
HIGH_CONFIDENCE = 90


@dataclass
class MatchResult:
    film: Film | None
    method: str  # 'override' | 'fuzzy' | 'ai' | 'none'
    confidence: float | None = None

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
    def __init__(
        self,
        tmdb: TMDBClient,
        overrides_path: Path = OVERRIDES_PATH,
        ai: AIMatcher | None = None,
    ) -> None:
        self.tmdb = tmdb
        self.ai = ai if ai is not None else AIMatcher()
        self.overrides = self._load_overrides(overrides_path)
        self._cache: dict[tuple[str, int | None], MatchResult] = {}

    @staticmethod
    def _load_overrides(path: Path) -> dict[str, int]:
        if not path.exists():
            return {}
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        # Keys are matched on their normalized form so listing noise is irrelevant.
        return {normalize_title(str(k)): int(v) for k, v in raw.items()}

    def match(self, raw_title: str, year: int | None = None) -> Film | None:
        return self.match_detailed(raw_title, year).film

    def match_detailed(self, raw_title: str, year: int | None = None) -> MatchResult:
        norm = normalize_title(raw_title)
        if not norm:
            return MatchResult(None, "none")
        cache_key = (norm, year)
        if cache_key not in self._cache:
            self._cache[cache_key] = self._resolve(raw_title, norm, year)
        return self._cache[cache_key]

    def _film(self, tmdb_id: int) -> Film | None:
        details = self.tmdb.movie_details(tmdb_id)
        return _film_from_details(details) if details else None

    def _resolve(self, raw_title: str, norm: str, year: int | None) -> MatchResult:
        # 1. Manual override always wins.
        if norm in self.overrides:
            film = self._film(self.overrides[norm])
            if film:
                return MatchResult(film, "override", 100.0)
            log.warning("Override for %r -> %s but no details", raw_title, self.overrides[norm])
            return MatchResult(None, "none")

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

        # High-confidence fuzzy is trusted outright (no AI call needed).
        if best_id is not None and best_score >= HIGH_CONFIDENCE:
            film = self._film(best_id)
            if film:
                return MatchResult(film, "fuzzy", best_score)

        # 3. AI adjudicates the uncertain middle band and rescues misses with candidates.
        if candidates and self.ai.enabled:
            ai_id, ai_conf = self.ai.pick(norm, candidates)
            if ai_id is not None:
                film = self._film(ai_id)
                if film:
                    return MatchResult(film, "ai", ai_conf)
            return MatchResult(None, "none")  # AI saw the candidates and rejected them

        # 4. No AI: fall back to the plain fuzzy threshold (original behaviour).
        if best_id is not None and best_score >= MATCH_THRESHOLD:
            film = self._film(best_id)
            if film:
                return MatchResult(film, "fuzzy", best_score)
        return MatchResult(None, "none")
