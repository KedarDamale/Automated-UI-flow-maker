"""
Page action extractor — finds every interactive element on the current page
and returns it as an ActionItem describing how to trigger it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page
    from .config import CrawlerConfig


# ─────────────────────────────────────────────
# Data type
# ─────────────────────────────────────────────

@dataclass
class ActionItem:
    label: str          # human-readable description
    selector: str       # CSS / playwright locator string
    tag: str            # underlying HTML tag
    role: str           # ARIA role (button, link, checkbox …)
    input_type: str     # for <input> elements
    href: str           # for <a> elements
    likely_navigates: bool = False
    weight: int = 1     # edge weight hint (navigates=2, in-page=1)


# ─────────────────────────────────────────────
# JS injected into the page to extract elements
# ─────────────────────────────────────────────

_EXTRACT_JS = """
() => {
    const SKIP_TAGS = new Set(['SCRIPT','STYLE','NOSCRIPT','SVG','HEAD']);
    const INTERACTIVE_ROLES = new Set([
        'button','link','menuitem','menuitemcheckbox','menuitemradio',
        'option','tab','checkbox','radio','switch','combobox','listbox'
    ]);

    function getLabel(el) {
        return (
            el.getAttribute('aria-label') ||
            el.getAttribute('title') ||
            el.getAttribute('placeholder') ||
            el.innerText?.trim().slice(0,80) ||
            el.getAttribute('name') ||
            el.getAttribute('id') ||
            el.tagName.toLowerCase()
        );
    }

    function uniqueSelector(el) {
        if (el.id) return '#' + CSS.escape(el.id);
        // build a path up to 4 levels deep
        let path = [];
        let cur = el;
        for (let i = 0; i < 4 && cur && cur !== document.body; i++) {
            let seg = cur.tagName.toLowerCase();
            if (cur.id) { seg = '#' + CSS.escape(cur.id); path.unshift(seg); break; }
            const siblings = Array.from(cur.parentElement?.children || [])
                .filter(c => c.tagName === cur.tagName);
            if (siblings.length > 1) {
                seg += ':nth-of-type(' + (siblings.indexOf(cur) + 1) + ')';
            }
            path.unshift(seg);
            cur = cur.parentElement;
        }
        return path.join(' > ');
    }

    function isVisible(el) {
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.height > 0 &&
               window.getComputedStyle(el).visibility !== 'hidden' &&
               window.getComputedStyle(el).display !== 'none';
    }

    const results = [];
    const seen = new Set();

    const candidates = document.querySelectorAll(
        'a[href], button, input:not([type=hidden]), select, textarea, ' +
        '[role="button"], [role="link"], [role="menuitem"], [role="tab"], ' +
        '[role="checkbox"], [role="radio"], [onclick]'
    );

    for (const el of candidates) {
        if (SKIP_TAGS.has(el.tagName)) continue;
        if (!isVisible(el)) continue;
        const sel = uniqueSelector(el);
        if (seen.has(sel)) continue;
        seen.add(sel);

        const tag = el.tagName.toLowerCase();
        const role = el.getAttribute('role') || '';
        const href = el.getAttribute('href') || '';
        const inputType = el.getAttribute('type') || '';
        const label = getLabel(el);

        const likelyNavigates = tag === 'a' && href && !href.startsWith('#') &&
                                 !href.startsWith('javascript');

        results.push({ label, selector: sel, tag, role, href, inputType, likelyNavigates });
    }
    return results;
}
"""


# ─────────────────────────────────────────────
# Public function
# ─────────────────────────────────────────────

async def extract_actions(page: "Page", cfg: "CrawlerConfig") -> list[ActionItem]:
    raw: list[dict] = await page.evaluate(_EXTRACT_JS)

    actions: list[ActionItem] = []
    for r in raw:
        label = r["label"] or r["tag"]
        selector = r["selector"]

        # skip unwanted selectors
        if _should_skip(selector, label, cfg):
            continue

        # filter by url allowlist if configured
        href = r.get("href", "")
        if cfg.url_allowlist_patterns and href:
            if not any(re.search(p, href) for p in cfg.url_allowlist_patterns):
                continue

        weight = 2 if r["likelyNavigates"] else 1

        actions.append(ActionItem(
            label=label,
            selector=selector,
            tag=r["tag"],
            role=r["role"],
            input_type=r.get("inputType", ""),
            href=href,
            likely_navigates=bool(r["likelyNavigates"]),
            weight=weight,
        ))

    # deduplicate by (label, tag) to avoid flooding on repeated nav items
    seen_labels: set[str] = set()
    deduped: list[ActionItem] = []
    for a in actions:
        key = f"{a.tag}::{a.label.lower()[:40]}"
        if key not in seen_labels:
            seen_labels.add(key)
            deduped.append(a)

    return deduped


def _should_skip(selector: str, label: str, cfg: "CrawlerConfig") -> bool:
    combined = (selector + " " + label).lower()
    for skip_sel in cfg.skip_selectors:
        if skip_sel.lower() in combined:
            return True
    # hard-coded safety skips
    danger_keywords = ["logout", "sign out", "delete account", "cancel subscription"]
    if any(kw in combined for kw in danger_keywords):
        return True
    return False
