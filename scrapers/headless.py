"""Headless-browser rendering via Playwright, for sites a plain HTTP client can't read:
either WAF-protected (Fondazione Prada / Cinema Godard returns 403 to non-browsers) or
JavaScript SPAs that build their content/API at runtime (Webtic).

Used only by the few scrapers that need it. Requires `playwright` + `playwright install chromium`.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def render_html(
    url: str,
    wait_until: str = "networkidle",
    wait_ms: int = 3000,
    wait_selector: str | None = None,
    timeout_ms: int = 45000,
) -> str:
    """Load `url` in headless Chromium and return the fully-rendered HTML."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(user_agent=BROWSER_UA, locale="it-IT")
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_load_state(wait_until, timeout=20000)
            except Exception:  # noqa: BLE001 - networkidle can legitimately time out
                pass
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=15000)
                except Exception:  # noqa: BLE001 - fall through with whatever rendered
                    log.warning("wait_selector %r not found on %s", wait_selector, url)
            page.wait_for_timeout(wait_ms)
            return page.content()
        finally:
            browser.close()
