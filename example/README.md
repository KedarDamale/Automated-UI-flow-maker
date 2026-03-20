# UI Flow Crawler

Crawls a website's frontend and produces a **UI flow graph** — nodes for each
screen/state, and edges for every interactive element that transitions between them.

Output format:
```json
{
  "start_node": "root_1",
  "nodes": {
    "root_1": {
      "type": "screen",
      "name": "Landing Page",
      "url": "https://example.com/",
      "tags": ["home"],
      "heuristics": {}
    },
    "login_2": {
      "type": "screen",
      "name": "Login",
      "url": "https://example.com/login",
      "tags": ["auth"],
      "heuristics": { "change_password": 5 }
    }
  },
  "adjacency_list": {
    "root_1": [
      {
        "to": "login_2",
        "weight": 2,
        "action": { "label": "Login", "selector": "#login-btn", "tag": "a", "href": "/login" }
      }
    ]
  },
  "meta": { "total_nodes": 12, "total_edges": 28 }
}
```

---

## Installation

```bash
pip install playwright anthropic
playwright install chromium
```

---

## Usage

### Public site (no login)
```bash
python run.py --url https://example.com --depth 3
```

### Site with login
```bash
# 1. Copy and edit the login steps template
cp login_steps.example.json login_steps.json
# edit selectors + credentials

# 2. Run
python run.py \
  --url https://app.example.com \
  --login-url https://app.example.com/login \
  --login-steps login_steps.json \
  --depth 4
```

### With LLM enrichment (better names + heuristics)
```bash
export ANTHROPIC_API_KEY=sk-ant-...

python run.py \
  --url https://app.example.com \
  --enrich \
  --tasks "change password,find invoice,update profile"
```

### Watch the browser (non-headless)
```bash
python run.py --url https://example.com --no-headless
```

### Save screenshots of every discovered state
```bash
python run.py --url https://example.com --screenshots ./shots
```

---

## All CLI options

| Flag | Default | Description |
|---|---|---|
| `--url` | required | Start URL |
| `--depth` | 3 | Max BFS depth |
| `--max-nodes` | 80 | Cap on nodes to discover |
| `--output` | output/ui_flow.json | Output file path |
| `--screenshots` | None | Directory for PNG screenshots |
| `--no-headless` | False | Show the browser window |
| `--login-url` | None | URL of the login page |
| `--login-steps` | None | Path to login steps JSON |
| `--enrich` | False | Call LLM to enrich metadata |
| `--tasks` | "" | Comma-separated task names for heuristics |
| `--api-key` | $ANTHROPIC_API_KEY | Anthropic API key |

---

## How it works

```
Start URL
   │
   ▼
Page Analyzer ──► extract all clickable/interactive elements
   │
   ▼
Action Executor ──► click / fill / select each element
   │
   ▼
State Differ ──► did URL or DOM change meaningfully?
   │  yes
   ▼
Graph Builder ──► new node + edge added
   │
   ▼ (loop via BFS queue)
JSON Output
```

**State detection** uses a multi-signal fingerprint:
- URL (with tracking params stripped)
- Page title
- First 3 headings
- Whether a modal/dialog is open
- Framework route hints (`data-page`, `data-route`)
- First 300 chars of main content

This means it correctly detects SPA transitions even when the URL doesn't change.

---

## Login steps format

```json
[
  { "selector": "#email",        "action": "fill",  "value": "user@example.com" },
  { "selector": "#password",     "action": "fill",  "value": "yourpassword" },
  { "selector": "[type=submit]", "action": "click" }
]
```

Supported actions: `fill`, `click`.

---

## Programmatic API

```python
import asyncio
import json
from crawler import CrawlerConfig, UICrawler, enrich_graph

cfg = CrawlerConfig(
    start_url="https://example.com",
    max_depth=3,
    login_url="https://example.com/login",
    login_steps=[
        {"selector": "#email",    "action": "fill",  "value": "user@x.com"},
        {"selector": "#password", "action": "fill",  "value": "secret"},
        {"selector": "[type=submit]", "action": "click"},
    ],
    screenshot_dir="./shots",
    skip_selectors=["[href*='logout']"],
)

async def run():
    graph = await UICrawler(cfg).crawl()
    graph = enrich_graph(graph, heuristic_tasks=["change password"])
    with open("output/flow.json", "w") as f:
        json.dump(graph, f, indent=2)

asyncio.run(run())
```

---

## Tips

- **Slow sites**: increase timeouts in `crawler.py` (`networkidle` timeout)
- **React/Vue/Angular**: the DOM fingerprinter handles most cases; if transitions are missed, add `data-page` or `data-route` attributes to your root component
- **Large apps**: start with `--depth 2 --max-nodes 30` to get an overview, then increase
- **Modals**: automatically detected as separate nodes with `"type": "modal"`
- **Forms**: by default, inputs are filled with dummy data — change `dummy_text` / `dummy_password` in config
