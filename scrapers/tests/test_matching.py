"""Tests for the title-matching core. Run with: python -m scrapers.tests.test_matching"""

from __future__ import annotations

from pathlib import Path

from ..matching import FilmMatcher, normalize_title
from ..tmdb import TMDBClient

FIXTURE_CACHE = Path(__file__).parent / "fixtures" / "tmdb.json"


def test_normalize_strips_noise_and_accents() -> None:
    assert normalize_title("Perfect Days (v.o. sub ita)") == "perfect days"
    assert normalize_title("La Città delle Donne (1980)") == "la citta delle donne"
    assert normalize_title("IL CASO (versione originale sottotitolata)") == "il caso"
    assert normalize_title("Stalker — 1979 restaurato") == "stalker"


def test_override_path(matcher: FilmMatcher) -> None:
    film = matcher.match("Perfect Days (v.o. sub ita)")
    assert film is not None and film.tmdb_id == 976893
    assert film.director == "Wim Wenders"


def test_fuzzy_search_path(matcher: FilmMatcher) -> None:
    film = matcher.match("La Chimera")
    assert film is not None and film.tmdb_id == 1042171


def test_unmatched_returns_none(matcher: FilmMatcher) -> None:
    assert matcher.match("Un Film Del Tutto Introvabile 1962") is None


def _run() -> None:
    # Hermetic: forced offline against the committed test fixture, never touches the network
    # or the production cache, regardless of whether TMDB_ACCESS_TOKEN is set.
    matcher = FilmMatcher(TMDBClient(cache_path=FIXTURE_CACHE, offline=True))
    test_normalize_strips_noise_and_accents()
    test_override_path(matcher)
    test_fuzzy_search_path(matcher)
    test_unmatched_returns_none(matcher)
    print("OK: all matching tests passed")


if __name__ == "__main__":
    _run()
