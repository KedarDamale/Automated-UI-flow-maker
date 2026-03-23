class GraphBuilder:
    def __init__(self):
        self._nodes: dict[str, dict] = {}           # node_id -> node dict
        self._adjacency: dict[str, list[dict]] = {} # node_id -> [edge, …]
        self._fp_to_id: dict[str, str] = {}         # fingerprint -> node_id
        self._start: str | None = None

    # ── mutation ─────────────────────────────

    def set_start(self, node_id: str):
        self._start = node_id

    def add_node(self, state: "CrawlState", fingerprint: str):
        # Infer a human-readable name from the page title
        name = _prettify(state.title or state.node_id)
        node_type = _infer_type(state.url, state.meta)

        self._nodes[state.node_id] = {
            "type": node_type,
            "name": name,
            "url": state.url,
            "tags": _infer_tags(state.url, state.title),
            "screenshot": state.screenshot_path,
            # placeholder for LLM-computed heuristics (see llm_enricher.py)
            "heuristics": {},
        }
        self._adjacency.setdefault(state.node_id, [])
        self._fp_to_id[fingerprint] = state.node_id

    def add_edge(self, src: str, dst: str, action: "ActionItem"):
        edges = self._adjacency.setdefault(src, [])
        # avoid duplicate edges to the same destination via the same selector
        for e in edges:
            if e["to"] == dst and e["action"]["selector"] == action.selector:
                return
        edges.append({
            "to": dst,
            "weight": action.weight,
            "action": {
                "label": action.label,
                "selector": action.selector,
                "tag": action.tag,
                "href": action.href or None,
            },
        })

    # ── query ────────────────────────────────

    def get_node(self, node_id: str) -> dict:
        return self._nodes.get(node_id, {})

    def fingerprint_to_id(self, fp: str) -> str | None:
        return self._fp_to_id.get(fp)

    # ── serialisation ────────────────────────

    def to_dict(self) -> dict:
        # Strip None values from edges for cleanliness
        adjacency_clean: dict[str, list] = {}
        for nid, edges in self._adjacency.items():
            adjacency_clean[nid] = [
                {k: v for k, v in e.items() if v is not None}
                for e in edges
            ]

        return {
            "start_node": self._start,
            "nodes": self._nodes,
            "adjacency_list": adjacency_clean,
            "meta": {
                "total_nodes": len(self._nodes),
                "total_edges": sum(len(v) for v in adjacency_clean.values()),
            },
        }


# ── helpers ──────────────────────────────────

def _prettify(title: str) -> str:
    """Strip common suffixes like ' - MyApp' or ' | Brand'."""
    for sep in [" - ", " | ", " — ", " · "]:
        if sep in title:
            title = title.split(sep)[0].strip()
    return title[:80]


def _infer_type(url: str, meta: dict) -> str:
    url_lower = url.lower()
    if any(k in url_lower for k in ["/modal", "modal=", "#modal"]):
        return "modal"
    if any(k in url_lower for k in ["/dialog", "dialog=", "#dialog"]):
        return "dialog"
    return "screen"


def _infer_tags(url: str, title: str) -> list[str]:
    combined = (url + " " + title).lower()
    tag_map = {
        "auth": ["login", "signin", "sign-in", "logout", "register", "signup", "sign-up",
                 "forgot-password", "reset-password", "verify", "otp"],
        "home": ["home", "dashboard", "overview", "index", "landing"],
        "settings": ["settings", "preferences", "account", "profile", "security"],
        "checkout": ["checkout", "payment", "billing", "cart", "order"],
        "search": ["search", "results", "filter"],
        "help": ["help", "support", "faq", "docs", "documentation"],
        "onboarding": ["onboarding", "welcome", "setup", "wizard", "getting-started"],
        "admin": ["admin", "manage", "management", "console", "panel"],
    }
    tags: list[str] = []
    for tag, keywords in tag_map.items():
        if any(kw in combined for kw in keywords):
            tags.append(tag)
    return tags
