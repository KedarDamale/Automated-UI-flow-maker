#!/usr/bin/env python3
"""
CLI entry point.

Basic usage (public site):
    python run.py --url https://example.com --depth 3

With login:
    python run.py --url https://app.example.com \
        --login-url https://app.example.com/login \
        --login-steps login_steps.json \
        --depth 4

With LLM enrichment:
    python run.py --url https://example.com \
        --enrich --tasks "change password,find invoice,update profile"
"""

import argparse
import asyncio
import json
import logging
import os
import sys

from crawler import CrawlerConfig, UICrawler, enrich_graph

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)


def parse_args():
    p = argparse.ArgumentParser(description="UI Flow Crawler")
    p.add_argument("--url", required=True, help="Start URL")
    p.add_argument("--depth", type=int, default=3, help="Max BFS depth (default 3)")
    p.add_argument("--max-nodes", type=int, default=80, help="Max nodes to discover")
    p.add_argument("--output", default="output/ui_flow.json", help="Output JSON path")
    p.add_argument("--screenshots", default=None, help="Dir to save screenshots")
    p.add_argument("--no-headless", action="store_true", help="Show browser window")
    p.add_argument("--stay-on-origin", action="store_true", default=True)

    # login
    p.add_argument("--login-url", default=None)
    p.add_argument(
        "--login-steps",
        default=None,
        help='JSON file with login steps, e.g. [{"selector":"#email","action":"fill","value":"user@x.com"},...]',
    )

    # LLM
    p.add_argument("--enrich", action="store_true", help="Enrich nodes with LLM metadata")
    p.add_argument(
        "--tasks",
        default="",
        help='Comma-separated task names for heuristic scoring, e.g. "change password,find billing"',
    )
    p.add_argument("--api-key", default=None, help="Anthropic API key (or set ANTHROPIC_API_KEY)")

    return p.parse_args()


async def main():
    args = parse_args()

    login_steps = []
    if args.login_steps:
        with open(args.login_steps) as f:
            login_steps = json.load(f)

    cfg = CrawlerConfig(
        start_url=args.url,
        max_depth=args.depth,
        max_nodes=args.max_nodes,
        headless=not args.no_headless,
        stay_on_origin=args.stay_on_origin,
        output_path=args.output,
        screenshot_dir=args.screenshots,
        login_url=args.login_url,
        login_steps=login_steps,
    )

    print(f"\n🔍  Crawling {args.url}  (depth={args.depth}, max_nodes={args.max_nodes})\n")
    crawler = UICrawler(cfg)
    graph = await crawler.crawl()

    if args.enrich:
        tasks = [t.strip() for t in args.tasks.split(",") if t.strip()]
        print(f"\n🤖  Enriching {len(graph['nodes'])} nodes with LLM …")
        graph = enrich_graph(graph, api_key=args.api_key, heuristic_tasks=tasks)

    # write output
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(graph, f, indent=2 if cfg.pretty_print else None)

    n = graph["meta"]["total_nodes"]
    e = graph["meta"]["total_edges"]
    print(f"\n✅  Done!  {n} nodes, {e} edges  →  {args.output}\n")


if __name__ == "__main__":
    asyncio.run(main())
