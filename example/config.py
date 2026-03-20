"""
Crawler configuration — all tuneable parameters in one place.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CrawlerConfig:
    


    # ── login (optional) ─────────────────────────────────────────────────
    login_url: str | None = None
    # list of {"selector": "...", "action": "fill|click", "value": "..."}
    login_steps: list[dict] = field(default_factory=list)

    # ── form dummy data ───────────────────────────────────────────────────
    dummy_text: str = "test"
    dummy_password: str = "Test@1234"

    # ── action filtering ──────────────────────────────────────────────────
    # CSS selectors to SKIP entirely (e.g. logout buttons, destructive actions)
    skip_selectors: list[str] = field(default_factory=lambda: [
        "[data-testid='logout']",
        "[href*='logout']",
        "[href*='signout']",
        "[href*='delete']",
        "[href*='remove']",
    ])
    # Only follow links matching these URL patterns (None = all)
    url_allowlist_patterns: list[str] = field(default_factory=list)

    # ── output ────────────────────────────────────────────────────────────
    output_path: str = "output/ui_flow.json"
    screenshot_dir: str | None = None      # set to a path to capture screenshots
    pretty_print: bool = True
