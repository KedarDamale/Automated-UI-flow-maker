"""
LLM enricher (optional) — calls the Anthropic API to:
  1. Generate better human-readable screen names
  2. Classify tags
  3. Compute task-specific heuristics (e.g. "how hard is it to reach
     the change-password screen from here?")

Usage:
    from crawler.llm_enricher import enrich_graph
    graph_dict = enrich_graph(graph_dict, api_key="sk-ant-...")

This module is OPTIONAL. If you don't call it, the graph still has
all structural information — just with auto-generated names.
"""
from __future__ import annotations

import json
import os

try:
    import anthropic
    _HAS_SDK = True
except ImportError:
    _HAS_SDK = False


_SYSTEM = """You are a UX analyst. Given a JSON description of a UI screen,
return a JSON object with:
  - "name": a short, clear screen name (≤5 words, Title Case)
  - "tags": list of relevant tags from: auth, home, settings, checkout, search,
    help, onboarding, admin, form, list, detail, modal, error
  - "heuristics": object mapping task names to difficulty scores 1-10
    (10 = very hard to complete this task from this screen).
    Use only tasks provided in the prompt.

Respond with ONLY valid JSON, no prose."""


def enrich_graph(
    graph: dict,
    api_key: str | None = None,
    heuristic_tasks: list[str] | None = None,
) -> dict:
    """
    Enrich every node in the graph with LLM-generated metadata.
    Mutates and returns the graph dict.
    """
    if not _HAS_SDK:
        print("[llm_enricher] anthropic SDK not installed — skipping. pip install anthropic")
        return graph

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("[llm_enricher] No API key — skipping enrichment.")
        return graph

    client = anthropic.Anthropic(api_key=key)
    tasks = heuristic_tasks or []

    for node_id, node in graph.get("nodes", {}).items():
        prompt = f"""Screen ID: {node_id}
URL: {node.get('url', '')}
Current name guess: {node.get('name', '')}
Current tags: {node.get('tags', [])}
Heuristic tasks to score: {tasks}

Return JSON only."""

        try:
            resp = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,
                system=_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            # strip markdown fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text)
            if "name" in data:
                node["name"] = data["name"]
            if "tags" in data:
                node["tags"] = list(set(node.get("tags", []) + data["tags"]))
            if "heuristics" in data:
                node["heuristics"] = data["heuristics"]
        except Exception as e:
            print(f"[llm_enricher] Failed for node {node_id}: {e}")

    return graph
