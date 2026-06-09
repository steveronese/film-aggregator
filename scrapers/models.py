"""Data models — the contract between the Python pipeline and the Astro site.

The scrapers emit `RawScreening`s. The orchestrator resolves each one to a canonical TMDB
`Film` and emits `Screening`s plus a deduplicated list of `Film`s. Everything written to
`data/*.json` validates against these models.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Language(str, Enum):
    """How the film is presented at this screening."""

    ORIGINAL = "original"          # original audio, no subtitles
    ORIGINAL_SUBBED = "original_subbed"  # original audio + Italian subtitles (VOS)
    DUBBED = "dubbed"              # Italian dub
    UNKNOWN = "unknown"

    @property
    def is_original(self) -> bool:
        return self in (Language.ORIGINAL, Language.ORIGINAL_SUBBED)


class Cinema(BaseModel):
    """A venue. Loaded from cinemas.yaml; written to data/cinemas.json for the site."""

    id: str
    name: str
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    website: str | None = None
    neighborhood: str | None = None
    # arthouse / museum / openair / multiplex — used for map markers & grouping.
    category: str | None = None


class RawScreening(BaseModel):
    """One screening as emitted by a scraper, before TMDB matching."""

    cinema_id: str
    raw_title: str
    raw_year: int | None = None
    start: datetime
    hall: str | None = None
    language: Language = Language.UNKNOWN
    booking_url: str | None = None
    source_url: str | None = None


class Film(BaseModel):
    """A canonical film, sourced entirely from TMDB."""

    tmdb_id: int
    title: str                     # Italian title (search done with language=it-IT)
    original_title: str | None = None
    italian_title: str | None = None
    year: int | None = None
    poster_path: str | None = None  # TMDB image path, e.g. "/abc.jpg"
    overview: str | None = None
    title_en: str | None = None      # English title + overview, for the EN version of the site
    overview_en: str | None = None
    runtime: int | None = None
    director: str | None = None
    genres: list[str] = Field(default_factory=list)


class Screening(BaseModel):
    """A RawScreening resolved against TMDB. `tmdb_id` is None when matching failed."""

    cinema_id: str
    tmdb_id: int | None = None
    raw_title: str
    start: datetime
    hall: str | None = None
    language: Language = Language.UNKNOWN
    booking_url: str | None = None
    source_url: str | None = None


class UnmatchedTitle(BaseModel):
    """A title we could not confidently match — triage these into overrides.yaml."""

    raw_title: str
    raw_year: int | None = None
    cinema_id: str
    occurrences: int = 1


class ReviewEntry(BaseModel):
    """A match worth a human glance — AI-picked or borderline-confidence. Catches false positives."""

    raw_title: str
    tmdb_id: int
    matched_title: str
    method: str  # 'fuzzy' | 'ai'
    confidence: float | None = None
