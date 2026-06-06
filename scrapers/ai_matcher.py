"""Optional LLM fallback for the hard title-matching cases — free to run.

It's free because it's invoked *only* on the handful of titles the fuzzy matcher can't resolve
confidently, and every answer is cached. That's a few calls per day — trivially inside a provider's
free tier. Default provider is Google Gemini (free API key, no card). When GEMINI_API_KEY is unset
the matcher is disabled and the pipeline behaves exactly as before.

The model never invents ids: it's given the real TMDB search candidates and must pick one (by id) or
say none, so it grounds, rather than hallucinates, the answer.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).parent / "cache" / "ai_matches.json"
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class AIMatcher:
    def __init__(self, cache_path: Path = CACHE_PATH, offline: bool = False) -> None:
        self.cache_path = cache_path
        self._cache: dict[str, Any] = self._load()
        self._dirty = False
        self.api_key = None if offline else os.environ.get("GEMINI_API_KEY")
        self.enabled = bool(self.api_key)
        self._client = httpx.Client(timeout=30.0)

    def _load(self) -> dict[str, Any]:
        if self.cache_path.exists():
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        return {}

    def save(self) -> None:
        if not self._dirty:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self._cache, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
        self._dirty = False

    def pick(self, norm_title: str, candidates: list[dict]) -> tuple[int | None, float | None]:
        """Return (tmdb_id, confidence) for the best matching candidate, or (None, None).

        `candidates` are raw TMDB search results. Cached by normalized title.
        """
        if norm_title in self._cache:
            c = self._cache[norm_title]
            return c.get("tmdb_id"), c.get("confidence")
        if not self.enabled or not candidates:
            return None, None

        valid_ids = {c["id"] for c in candidates}
        result = self._ask(norm_title, candidates)
        tmdb_id = result.get("tmdb_id") if result else None
        conf = result.get("confidence") if result else None
        if tmdb_id not in valid_ids:  # reject anything not grounded in the candidates
            tmdb_id, conf = None, None
        self._cache[norm_title] = {"tmdb_id": tmdb_id, "confidence": conf}
        self._dirty = True
        return tmdb_id, conf

    def _ask(self, norm_title: str, candidates: list[dict]) -> dict | None:
        lines = []
        for c in candidates[:8]:
            year = (c.get("release_date") or "")[:4]
            lines.append(
                f"- id={c['id']} | \"{c.get('title')}\" / original \"{c.get('original_title')}\""
                f" ({year or '?'})"
            )
        prompt = (
            "Match a cinema listing to The Movie Database (TMDB).\n"
            f'Listing title (Italian, may contain extra words): "{norm_title}"\n\n'
            "Candidate TMDB films:\n" + "\n".join(lines) + "\n\n"
            "Reply with JSON {\"tmdb_id\": <id of the same film, or null>, "
            "\"confidence\": <0-100>}. Choose a candidate only if you are confident it is the "
            "same film; otherwise use null."
        )
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }
        try:
            resp = self._client.post(
                ENDPOINT.format(model=DEFAULT_MODEL),
                params={"key": self.api_key},
                json=body,
            )
            resp.raise_for_status()
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
            log.warning("AI match failed for %r: %s", norm_title, exc)
            return None
