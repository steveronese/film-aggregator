"""Optional LLM fallback for the hard title-matching cases — free to run.

It's free because it's invoked *only* on the handful of titles the fuzzy matcher can't resolve
confidently, and every answer is cached. That's a few calls per day — trivially inside a provider's
free tier. Provider is Mistral (EU-based, free API tier — works from Italy, unlike Gemini's
EU-excluded free tier). When MISTRAL_API_KEY is unset the matcher is disabled and the pipeline
behaves exactly as before.

The endpoint is OpenAI-compatible, so MISTRAL_BASE_URL/MISTRAL_MODEL can point it at Groq, a local
Ollama, or any compatible API instead. The model never invents ids: it's given the real TMDB search
candidates and must pick one (by id) or say none.
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
BASE_URL = os.environ.get("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")
MODEL = os.environ.get("MISTRAL_MODEL", "mistral-small-latest")


class AIMatcher:
    def __init__(self, cache_path: Path = CACHE_PATH, offline: bool = False) -> None:
        self.cache_path = cache_path
        self._cache: dict[str, Any] = self._load()
        self._dirty = False
        self.api_key = None if offline else os.environ.get("MISTRAL_API_KEY")
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

    def pick(self, norm_title: str, candidates: list[dict],
             raw_title: str | None = None) -> tuple[int | None, float | None]:
        """Return (tmdb_id, confidence) for the best matching candidate, or (None, None).
        Cached by normalized title."""
        if norm_title in self._cache:
            c = self._cache[norm_title]
            return c.get("tmdb_id"), c.get("confidence")
        if not self.enabled or not candidates:
            return None, None

        valid_ids = {c["id"] for c in candidates}
        result = self._ask(raw_title or norm_title, candidates)
        tmdb_id = result.get("tmdb_id") if result else None
        conf = result.get("confidence") if result else None
        if tmdb_id not in valid_ids:  # reject anything not grounded in the candidates
            tmdb_id, conf = None, None
        self._cache[norm_title] = {"tmdb_id": tmdb_id, "confidence": conf}
        self._dirty = True
        return tmdb_id, conf

    def _ask(self, listing_title: str, candidates: list[dict]) -> dict | None:
        lines = []
        for c in candidates[:8]:
            year = (c.get("release_date") or "")[:4]
            lines.append(
                f"- id={c['id']} | \"{c.get('title')}\" / original \"{c.get('original_title')}\""
                f" ({year or '?'}, popularity {round(c.get('popularity') or 0, 1)})"
            )
        prompt = (
            "Match a cinema listing to the correct The Movie Database (TMDB) film.\n"
            f'Cinema listing title (Italian; a foreign original title often appears in parentheses): '
            f'"{listing_title}"\n\n'
            "Candidate TMDB films:\n" + "\n".join(lines) + "\n\n"
            "Rules:\n"
            "- If the listing shows a foreign original title in parentheses, pick the candidate whose "
            "ORIGINAL title matches it (not merely the Italian title — several different films can share "
            "the same Italian title).\n"
            "- These are CURRENT cinema screenings, so when titles tie, prefer the most recent release / "
            "higher popularity, UNLESS the listing clearly marks a restored classic or retrospective.\n"
            '- Reply ONLY with JSON {"tmdb_id": <id, or null>, "confidence": <0-100>}. '
            "Use null if no candidate is clearly the same film."
        )
        body = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        try:
            resp = self._client.post(
                f"{BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]
            return json.loads(text)
        except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
            log.warning("AI match failed for %r: %s", norm_title, exc)
            return None
