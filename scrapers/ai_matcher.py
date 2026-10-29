"""Optional LLM fallback for the hard title-matching cases — free to run.

It's free because it's invoked *only* on the handful of titles the fuzzy matcher can't resolve
confidently, and every answer is cached. That's a few calls per day — trivially inside a provider's
free tier. When no API key is set the matcher is disabled and the pipeline behaves exactly as before.

Any OpenAI-compatible chat endpoint works, configured via AI_BASE_URL / AI_MODEL / AI_API_KEY:
  - CI uses GitHub Models with the workflow's own GITHUB_TOKEN — no account or key to expire, which
    keeps the daily job self-sufficient (see .github/workflows/scrape.yml).
  - Locally, the legacy MISTRAL_* variables still work as a fallback (Mistral is the default).
The model never invents ids: it's given the real TMDB search candidates and must pick one (by id)
or say none.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).parent / "cache" / "ai_matches.json"
BASE_URL = os.environ.get("AI_BASE_URL") or os.environ.get("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")
MODEL = os.environ.get("AI_MODEL") or os.environ.get("MISTRAL_MODEL", "mistral-small-latest")
# Free tiers cap requests per minute (GitHub Models' low tier: 15/min), so pace calls rather than
# burst into 429s. Uncached calls are rare after the first run, so this costs little.
MIN_INTERVAL = float(os.environ.get("AI_MIN_INTERVAL", "4.5"))
_MAX_RETRIES = 2


class AIMatcher:
    def __init__(self, cache_path: Path = CACHE_PATH, offline: bool = False) -> None:
        self.cache_path = cache_path
        self._cache: dict[str, Any] = self._load()
        self._dirty = False
        self.api_key = None if offline else (os.environ.get("AI_API_KEY") or os.environ.get("MISTRAL_API_KEY"))
        self._configured = bool(self.api_key)
        self._client = httpx.Client(timeout=30.0)
        self._last_call = 0.0
        # Circuit breaker: after too many consecutive API failures (the free tier rate-limiting us
        # with 429s, or an outage), stop calling the provider for the rest of the run. Every doomed
        # call otherwise costs a throttled round-trip, spams the log, and — worst of all, before this
        # existed — a bug in the error path could sink the whole pipeline. Falling back to no-AI
        # matching degrades gracefully: fuzzy matches still land, the rest go to unmatched.json.
        self._consecutive_failures = 0
        self._tripped = False

    _FAILURE_LIMIT = 5

    @property
    def enabled(self) -> bool:
        return self._configured and not self._tripped

    def _note_failure(self, exc: Exception) -> None:
        self._consecutive_failures += 1
        if not self._tripped and self._consecutive_failures >= self._FAILURE_LIMIT:
            self._tripped = True
            log.warning(
                "AI matcher disabled for the rest of this run after %d consecutive failures "
                "(last: %s). Continuing with fuzzy matching only.",
                self._consecutive_failures, exc,
            )

    def _note_success(self) -> None:
        self._consecutive_failures = 0

    def _chat(self, prompt: str) -> dict:
        """POST one JSON-mode chat completion and return the parsed JSON reply. Paces calls to
        MIN_INTERVAL and retries 429s (honouring Retry-After, capped). Raises on failure — the
        callers record it for the circuit breaker."""
        body = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        for attempt in range(_MAX_RETRIES + 1):
            wait = MIN_INTERVAL - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
            resp = self._client.post(
                f"{BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
            if resp.status_code == 429 and attempt < _MAX_RETRIES:
                retry_after = resp.headers.get("Retry-After", "")
                time.sleep(min(float(retry_after), 60.0) if retry_after.isdigit() else 10.0 * (attempt + 1))
                continue
            resp.raise_for_status()
            return json.loads(resp.json()["choices"][0]["message"]["content"])
        raise AssertionError("unreachable")

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
        if result is None:
            # API call failed (e.g. a 429) — don't cache, so a transient failure doesn't poison
            # the committed cache and permanently mark this title unmatchable.
            return None, None
        tmdb_id = result.get("tmdb_id")
        conf = result.get("confidence")
        if tmdb_id not in valid_ids:  # reject anything not grounded in the candidates
            tmdb_id, conf = None, None
        self._cache[norm_title] = {"tmdb_id": tmdb_id, "confidence": conf}
        self._dirty = True
        return tmdb_id, conf

    def extract_title(self, raw_title: str) -> dict | None:
        """Robust fallback: have the LLM strip a messy listing down to the film's canonical title
        (+ year) so we can re-search TMDB. Returns {"title", "year"} (title="" if it's not a film),
        or None on error. Cached."""
        key = "::extract::" + raw_title.lower()
        if key in self._cache:
            return self._cache[key]
        if not self.enabled:
            return None
        prompt = (
            "A raw cinema listing title (Italian) is given. Extract ONLY the film's canonical title, "
            "removing hall/format/edition/event tags such as 'Sala XL', '3D', 'IMAX', 'Vm14', 'Ried.', "
            "'4K', 'Ed. Rest.', anniversary marks ('40°'), and add-ons ('+ Talk con …', '+ Live', "
            "'Masterclass …', 'Incontro con …'). Keep any foreign original title shown in parentheses. "
            "If the listing is NOT a film (an exhibition, masterclass, or talk), return an empty title.\n"
            f'Listing: "{raw_title}"\n'
            'Reply ONLY JSON {"title": "<clean title or empty>", "year": <year shown or null>}.'
        )
        try:
            data = self._chat(prompt)
            title = (data.get("title") or "").strip()
            year = data.get("year")
            result = {"title": title, "year": year if isinstance(year, int) else None}
            self._note_success()
        except (httpx.HTTPError, KeyError, IndexError, TypeError, AttributeError, json.JSONDecodeError) as exc:
            self._note_failure(exc)
            log.warning("AI extract failed for %r: %s", raw_title, exc)
            return None
        self._cache[key] = result
        self._dirty = True
        return result

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
        try:
            parsed = self._chat(prompt)
            if not isinstance(parsed, dict):
                raise TypeError(f"expected a JSON object, got {type(parsed).__name__}")
            self._note_success()
            return parsed
        except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            self._note_failure(exc)
            log.warning("AI match failed for %r: %s", listing_title, exc)
            return None
