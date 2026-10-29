"""Shared, polite HTTP client for scrapers.

Good-citizen behaviour: identify the bot in the User-Agent, set a sane timeout, and rate-limit
requests to each host so we never hammer a small arthouse cinema's server.
"""

from __future__ import annotations

import time
from urllib.parse import urlparse

import httpx

USER_AGENT = (
    "MilanFilmAggregatorBot/0.1 (+https://github.com/your-org/film-aggregator; "
    "non-commercial cinema listings aggregator)"
)

# Minimum seconds between requests to the same host.
_MIN_INTERVAL = 1.0
_last_request: dict[str, float] = {}

# On HTTP 429 (rate limited) retry a few times with exponential backoff before giving up. Some
# backends (notably 18tickets' per-film title pages) rate-limit bursts even at _MIN_INTERVAL, so a
# short backoff recovers most of those requests instead of losing the film's title.
_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0


def _throttle(url: str) -> None:
    host = urlparse(url).netloc
    now = time.monotonic()
    last = _last_request.get(host)
    if last is not None:
        wait = _MIN_INTERVAL - (now - last)
        if wait > 0:
            time.sleep(wait)
    _last_request[host] = time.monotonic()


def make_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept-Language": "it-IT,it;q=0.9,en;q=0.6"},
        timeout=20.0,
        follow_redirects=True,
    )


def _retry_after(resp: httpx.Response, attempt: int) -> float:
    """Seconds to wait before retrying a 429: honour the Retry-After header if sane, else back off."""
    header = resp.headers.get("Retry-After")
    if header and header.isdigit():
        return min(float(header), 30.0)
    return _BACKOFF_BASE * (2 ** attempt)


def _request(client: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response:
    """Issue a throttled request, retrying on 429 with backoff. Raises for other HTTP errors."""
    for attempt in range(_MAX_RETRIES + 1):
        _throttle(url)
        resp = client.request(method, url, **kwargs)
        if resp.status_code == 429 and attempt < _MAX_RETRIES:
            time.sleep(_retry_after(resp, attempt))
            continue
        resp.raise_for_status()
        return resp
    resp.raise_for_status()  # exhausted retries on 429
    return resp


def get(client: httpx.Client, url: str, **kwargs) -> httpx.Response:
    """GET with per-host throttling and 429 backoff. Raises for HTTP errors."""
    return _request(client, "GET", url, **kwargs)


def post(client: httpx.Client, url: str, **kwargs) -> httpx.Response:
    """POST with per-host throttling and 429 backoff. Raises for HTTP errors."""
    return _request(client, "POST", url, **kwargs)
