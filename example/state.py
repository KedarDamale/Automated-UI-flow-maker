"""
Page state fingerprinting — produces a stable hash that changes when the
user would perceive a meaningful state transition, even in SPAs where the
URL might stay the same.
"""
from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page


_FINGERPRINT_JS = """
() => {
    // Collect signals that indicate a distinct UI state
    const url = location.href;
    const title = document.title;

    // Main headings
    const h1 = Array.from(document.querySelectorAll('h1,h2'))
        .slice(0, 3)
        .map(e => e.innerText.trim())
        .join('|');

    // Modal / dialog open?
    const modalOpen = !!(
        document.querySelector('[role="dialog"][aria-hidden="false"]') ||
        document.querySelector('.modal.show, .modal.is-open, [data-modal="open"]') ||
        document.querySelector('[role="alertdialog"]')
    );

    // Active route hint from popular frameworks
    const routerView = document.querySelector('[data-page], [data-route], .active-page');
    const routeHint = routerView?.dataset?.page || routerView?.dataset?.route || '';

    // Primary content hash (first 300 chars of main/article/body text)
    const mainEl = document.querySelector('main, [role="main"], article') || document.body;
    const textSnippet = mainEl.innerText?.trim().slice(0, 300) || '';

    // Number of top-level nav items (structural signal)
    const navCount = document.querySelectorAll('nav a, [role="navigation"] a').length;

    return { url, title, h1, modalOpen, routeHint, textSnippet, navCount };
}
"""


async def fingerprint_page(page: "Page") -> str:
    """Return a stable hex hash representing the current UI state."""
    try:
        signals: dict = await page.evaluate(_FINGERPRINT_JS)
    except Exception:
        # fallback to just url + title
        signals = {"url": page.url, "title": await page.title()}

    # Normalise URL: strip query params that are tracking/pagination noise
    url = signals.get("url", "")
    # keep path + meaningful query keys but drop noisy ones
    from urllib.parse import urlparse, parse_qs, urlencode
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    NOISE_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "ref", "fbclid", "_ga"}
    clean_qs = {k: v for k, v in qs.items() if k not in NOISE_PARAMS}
    clean_url = parsed._replace(query=urlencode(clean_qs, doseq=True)).geturl()
    signals["url"] = clean_url

    blob = json.dumps(signals, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()
