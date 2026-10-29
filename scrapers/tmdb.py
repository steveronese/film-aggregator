"""Thin TMDB API client with an on-disk cache.

Caching is essential to "cheap to run": we only ever call TMDB during the scheduled scrape, and
repeated titles (a film runs for weeks across many cinemas) hit the cache. The cache is committed
so builds are reproducible and work offline.

Auth: set TMDB_ACCESS_TOKEN (v4 read token, preferred) or TMDB_API_KEY (v3). With neither, the
client runs in cache-only mode — useful for offline development and tests.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

API_BASE = "https://api.themoviedb.org/3"
DEFAULT_CACHE = Path(__file__).parent / "cache" / "tmdb.json"

# The cache is committed daily, so it must stay small: full TMDB responses (entire cast & crew,
# every language's translation) grew it past 40 MB — headed for GitHub's 100 MB hard limit, which
# would make the daily push fail. Keep only the fields matching.py / ai_matcher.py read.
_SEARCH_FIELDS = ("id", "title", "original_title", "release_date", "popularity")
_MOVIE_FIELDS = ("id", "title", "original_title", "release_date", "poster_path", "overview", "runtime")


def _slim_search(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: r.get(k) for k in _SEARCH_FIELDS} for r in results]


def _slim_movie(d: dict[str, Any]) -> dict[str, Any]:
    out = {k: d.get(k) for k in _MOVIE_FIELDS}
    out["genres"] = [{"name": g.get("name")} for g in d.get("genres") or []]
    crew = (d.get("credits") or {}).get("crew") or []
    out["credits"] = {"crew": [{"name": c.get("name"), "job": "Director"}
                               for c in crew if c.get("job") == "Director"]}
    out["translations"] = {"translations": [
        {"iso_639_1": "en", "data": {"title": (t.get("data") or {}).get("title"),
                                     "overview": (t.get("data") or {}).get("overview")}}
        for t in (d.get("translations") or {}).get("translations") or [] if t.get("iso_639_1") == "en"
    ]}
    return out


class TMDBClient:
    def __init__(self, cache_path: Path = DEFAULT_CACHE, offline: bool = False) -> None:
        self.cache_path = cache_path
        self._migrated = False
        self._cache: dict[str, Any] = self._load_cache()
        self._dirty = self._migrated  # persist a slimmed cache even if no new lookups happen

        token = os.environ.get("TMDB_ACCESS_TOKEN")
        api_key = os.environ.get("TMDB_API_KEY")
        self._params: dict[str, str] = {}
        headers = {"Accept": "application/json"}
        if offline:
            self._online = False
        elif token:
            headers["Authorization"] = f"Bearer {token}"
            self._online = True
        elif api_key:
            self._params["api_key"] = api_key
            self._online = True
        else:
            self._online = False
            log.warning("No TMDB credentials set — running in cache-only mode.")
        self._client = httpx.Client(base_url=API_BASE, headers=headers, timeout=20.0)

    # ---- cache plumbing ----------------------------------------------------
    def _load_cache(self) -> dict[str, Any]:
        if not self.cache_path.exists():
            return {"search": {}, "movie": {}}
        cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
        # Migrate entries written before slimming existed (idempotent: slim(slim(x)) == slim(x)).
        search = {k: _slim_search(v) for k, v in cache.get("search", {}).items()}
        movie = {k: _slim_movie(v) for k, v in cache.get("movie", {}).items()}
        if search != cache.get("search") or movie != cache.get("movie"):
            self._migrated = True
        return {"search": search, "movie": movie}

    def save_cache(self) -> None:
        if not self._dirty:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self._cache, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        self._dirty = False

    def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any] | None:
        if not self._online:
            return None
        try:
            resp = self._client.get(path, params={**self._params, **params})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            log.error("TMDB request failed (%s): %s", path, exc)
            return None

    # ---- API ---------------------------------------------------------------
    def search_movie(self, query: str, year: int | None = None) -> list[dict[str, Any]]:
        key = f"{query}|{year or ''}"
        cached = self._cache["search"].get(key)
        if cached is not None:
            return cached
        params: dict[str, Any] = {"query": query, "language": "it-IT", "region": "IT"}
        if year:
            params["year"] = year
        data = self._request("/search/movie", params)
        results = (data or {}).get("results", [])
        if data is not None:
            results = _slim_search(results)
            self._cache["search"][key] = results
            self._dirty = True
        return results

    def movie_details(self, tmdb_id: int) -> dict[str, Any] | None:
        key = str(tmdb_id)
        cached = self._cache["movie"].get(key)
        if cached is not None:
            return cached
        data = self._request(
            f"/movie/{tmdb_id}", {"language": "it-IT", "append_to_response": "credits,translations"}
        )
        if data is not None:
            data = _slim_movie(data)
            self._cache["movie"][key] = data
            self._dirty = True
        return data
