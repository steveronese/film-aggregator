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
from datetime import date
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
CURRENT_YEAR = date.today().year


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

# Hall / format / edition tags that get added to listing titles and break matching, e.g.
# "(Sala XL) Backrooms", "3d - Supergirl", "Backrooms Vm14", "The Doors 4k (Ried. 2026)",
# "A qualcuno piace caldo (Ed. Rest.)", "Stand By Me 40° Ann.". Stripped before matching; kept
# narrow so it never eats a real title word.
_FORMAT = re.compile(
    r"\b(sala\s+\w+|schermo\s+\w+|imax|4dx|screenx|3d|2d|hfr|atmos|dolby(\s+atmos)?|"
    r"vip|gold|xl|kor|orig|"
    r"v\.?\s*m\.?\s*\d{1,2}|vm\d{1,2}|"            # age rating: Vm14 / V.M.14
    r"ried\.?|riedizione|"                          # re-release
    r"[248]k|"                                       # 4K / 2K / 8K
    r"ed\.?\s*rest\w*|restaurat\w*|"                 # restored edition
    r"comics|vol\.?\s*\d+)\b",
    re.IGNORECASE,
)
# Tags ending in a non-word char (so they can't use a trailing \b): "40°", "40 ann.", "Rest.".
_FORMAT_SYM = re.compile(r"\b\d{1,3}\s*(°|ann(i|iversario)?\b\.?)|\brest\.|\bann\.", re.IGNORECASE)
# Event add-ons appended after the film, e.g. "Le Lac + Talk con Fabrice", "La cronologia + Live".
_EVENT_SUFFIX = re.compile(r"\s+\+\s+.*$|\s+(?:incontro|talk|q&a|dibattito|live)\b.*$", re.IGNORECASE)


def normalize_title(title: str) -> str:
    """Lowercase, strip accents and listing noise, drop trailing year, collapse punctuation."""
    title = _EVENT_SUFFIX.sub("", title)  # drop "+ Talk con …", "… Live" event add-ons
    text = unicodedata.normalize("NFKD", title)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = _NOISE.sub(" ", text)
    text = _FORMAT.sub(" ", text)
    text = _FORMAT_SYM.sub(" ", text)
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

    def _best(self, norm: str, candidates: list[dict]):
        """Score candidates (best over Italian/original title), then sort by score, then by TMDB
        popularity. Popularity is the decisive tie-break for same-titled films: cinemas show current
        releases, which are far more popular than decades-old namesakes (Supergirl 2026 ≫ 1984;
        Lo straniero / Ozon 2025 > Visconti 1967). Returns (best_score, best_cand)."""
        scored: list[tuple[float, float, dict]] = []
        for cand in candidates:
            score = max(
                (fuzz.token_sort_ratio(norm, normalize_title(cand.get(f) or ""))
                 for f in ("title", "original_title") if cand.get(f)),
                default=0,
            )
            if score > 0:
                scored.append((score, cand.get("popularity") or 0.0, cand))
        scored.sort(key=lambda t: (-t[0], -t[1]))
        best_score = scored[0][0] if scored else 0.0
        best_cand = scored[0][2] if scored else None
        return best_score, best_cand

    def _deep_ai(self, raw_title: str, norm: str, year: int | None) -> MatchResult | None:
        """Have the LLM extract a clean title from the messy listing, then re-search TMDB and match."""
        cleaned = self.ai.extract_title(raw_title)
        if not cleaned or not cleaned.get("title"):
            return None
        norm2 = normalize_title(cleaned["title"])
        if not norm2 or norm2 == norm:
            return None  # nothing new to try
        candidates = self.tmdb.search_movie(norm2, cleaned.get("year") or year)
        if not candidates:
            return None
        best_score, best_cand = self._best(norm2, candidates)
        if best_cand is not None and best_score >= HIGH_CONFIDENCE:
            film = self._film(best_cand["id"])
            if film:
                return MatchResult(film, "ai", best_score)
        ai_id, conf = self.ai.pick(norm2, candidates, raw_title=cleaned["title"])
        if ai_id is not None:
            film = self._film(ai_id)
            if film:
                return MatchResult(film, "ai", conf)
        return None

    def _resolve(self, raw_title: str, norm: str, year: int | None) -> MatchResult:
        # 1. Manual override always wins.
        if norm in self.overrides:
            film = self._film(self.overrides[norm])
            if film:
                return MatchResult(film, "override", 100.0)
            log.warning("Override for %r -> %s but no details", raw_title, self.overrides[norm])
            return MatchResult(None, "none")

        # 2. Fuzzy search against TMDB; trust a high-confidence (popularity-tiebroken) match outright.
        #    Popularity is more reliable than the small LLM at same-title year disambiguation, so we
        #    do NOT send these to the AI.
        candidates = self.tmdb.search_movie(norm, year)
        best_score, best_cand = self._best(norm, candidates)
        if best_cand is not None and best_score >= HIGH_CONFIDENCE:
            film = self._film(best_cand["id"])
            if film:
                return MatchResult(film, "fuzzy", best_score)

        # 3. AI handles the uncertain band (messy / foreign-title cases), using the raw title (which
        #    keeps the foreign original title in parentheses) and the candidates' details.
        if candidates and self.ai.enabled:
            ai_id, ai_conf = self.ai.pick(norm, candidates, raw_title=raw_title)
            if ai_id is not None:
                film = self._film(ai_id)
                if film:
                    return MatchResult(film, "ai", ai_conf)

        # 3b. Robust fallback: let the LLM strip the messy listing to a clean title, then re-search.
        #     Catches arbitrary noise (Vm14, Ried., "+ Talk con …") and titles our search missed.
        if self.ai.enabled:
            deep = self._deep_ai(raw_title, norm, year)
            if deep is not None:
                return deep
            return MatchResult(None, "none")  # AI exhausted its options

        # 4. No AI: accept the best (popularity-tiebroken) fuzzy match above threshold.
        if best_cand is not None and best_score >= MATCH_THRESHOLD:
            film = self._film(best_cand["id"])
            if film:
                return MatchResult(film, "fuzzy", best_score)
        return MatchResult(None, "none")
