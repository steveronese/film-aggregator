"""Base scraper interface. Each cinema implements one `BaseScraper` subclass."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import httpx

from .http import get, make_client
from .models import RawScreening

log = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Subclass per cinema (or per shared ticketing backend).

    Implementations should:
      - set `cinema_id` to match an entry in cinemas.yaml,
      - implement `fetch()` to return upcoming RawScreenings,
      - use `self.get(url)` for polite, throttled HTTP.
    """

    #: Must match a cinema id in cinemas.yaml.
    cinema_id: str = ""

    def __init__(self, client: httpx.Client | None = None) -> None:
        if not self.cinema_id:
            raise ValueError(f"{type(self).__name__} must set cinema_id")
        self._client = client or make_client()

    def get(self, url: str, **kwargs) -> httpx.Response:
        return get(self._client, url, **kwargs)

    @abstractmethod
    def fetch(self) -> list[RawScreening]:
        """Return all currently-known upcoming screenings for this cinema."""

    def fetch_safe(self) -> list[RawScreening]:
        """fetch() wrapper that logs and swallows errors so one broken cinema
        never sinks the whole run."""
        try:
            screenings = self.fetch()
            log.info("%s: %d screenings", self.cinema_id, len(screenings))
            return screenings
        except Exception as exc:  # noqa: BLE001 - intentional: isolate per-cinema failures
            log.error("%s: scraper failed: %s", self.cinema_id, exc)
            return []
