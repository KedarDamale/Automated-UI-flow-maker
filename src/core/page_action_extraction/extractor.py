from pydantic import BaseModel
import re
from playwright.async_api import Page
from src.config.Config import settings

class ActionItem(BaseModel):
    label: str          
    selector: str       
    tag: str            
    role: str           
    input_type: str     
    href: str           
    likely_navigates: bool = False
    weight: int = 1 

def should_skip(selector: str, label: str)-> bool:

    combined = (selector + " " + label).lower()
    for skip_sel in settings.SKIP_SELECTORS:
        if skip_sel.lower() in combined:
            return True
    danger_keywords = ["logout", "sign out", "delete account", "cancel subscription"]
    if any(kw in combined for kw in danger_keywords):
        return True
    return False

async def extract_actions(page: "Page", cfg: "CrawlerConfig") -> list[ActionItem]:
    raw: list[dict] = await page.evaluate(settings.EXTRACT_JS)

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




    