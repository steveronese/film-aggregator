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


def get(client: httpx.Client, url: str, **kwargs) -> httpx.Response:
    """GET with per-host throttling. Raises for HTTP errors."""
    _throttle(url)
    resp = client.get(url, **kwargs)
    resp.raise_for_status()
    return resp


def post(client: httpx.Client, url: str, **kwargs) -> httpx.Response:
    """POST with per-host throttling. Raises for HTTP errors."""
    _throttle(url)
    resp = client.post(url, **kwargs)
    resp.raise_for_status()
    return resp
