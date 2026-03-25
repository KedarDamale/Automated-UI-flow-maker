from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Set



class Config(BaseSettings):

    #llm config
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_API_VERSION: str
    AZURE_DEPLOYMENT_NAME: str
    LLM_ENRICH:bool=True
    CHAR_LIMIT:int=100_000 * 4 # 400k tokens
    
    SYSTEM_PROMPT:str="""
                        You are a UX analyst. Given a list of UI screen nodes, enrich each one.
                        For each node return a JSON object keyed by node id with these fields:
                        - "name": short screen name, 5 words max, Title Case
                        - "summary": 2-3 sentences. Describe what this screen is, what the user can see, and what they can do here.
                        - "user_intents": list of 3-6 natural language goals a user might have when landing on this screen.
                        - "tags": list from: auth, home, settings, checkout, search, help, onboarding, admin, form, list, detail, modal, error, nav, landing, docs, media
                        - "content_type": one of: form, article, listing, dashboard, landing, modal, nav, media, error
                        - "complexity": number 1-5. How complex is this screen? 1=single action, 5=many sections and interactions.
                        - "heuristics": object mapping each inferred user intent to a difficulty score 1-10.
                        10 = very hard to complete from this screen, 1 = trivially easy.

                        Rules:
                        - user_intents must be specific to what this screen actually offers, not generic.
                        - summary must mention concrete UI elements visible on the screen (forms, buttons, lists, etc).
                        - Respond with ONLY valid JSON, no prose, no markdown fences.
    """

    EXTRACT_JS:str="""() => {
    const SKIP_TAGS = new Set(['SCRIPT','STYLE','NOSCRIPT','SVG','HEAD']);

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
}"""
    #crawl config
    CRAWL_URL: str="https://patgpt.globalspace.in"
    MAX_DEPTH: int=1000000000
    MAX_NODES: int=1000000000
    STAY_ON_ORIGIN: bool = True

    DUMMY_TEXT:str="kedardamale@gmail.com"
    DUMMY_PASSWORD:str="kedar152004"
    #browser config
    BROWSER_HEADLESS:bool=True
    BROWSER_VIEWPORT:dict | None = Field(default_factory=lambda: {"width": 1280, "height": 800})
    BROWSER_EXTRA_HEADERS:dict = Field(default_factory=dict)

    #cookie config
    COOKIES:list[dict] = Field(default_factory=list)

    #login details
    LOGIN_URL:str | None = None
        # list of {"selector": "...", "action": "fill|click", "value": "..."}
    LOGIN_STEPS: list[dict] = Field(default_factory=list)
    LOGIN_USERNAME:str | None = None
    LOGIN_PASSWORD:str | None = None

    #action filtering
    SKIP_SELECTORS: list[str] = Field(default_factory=lambda: [
        "[data-testid='logout']",
        "[href*='logout']",
        "[href*='signout']",
        "[href*='delete']",
        "[href*='remove']",
    ])
    # Only follow links matching these URL patterns (None = all)
    URL_ALLOWLIST_PATTERNS: list[str] = Field(default_factory=list)
    NOISE_PARAMS:Set[str] = Field(default_factory=lambda: {"utm_source", "utm_medium", "utm_campaign", "ref", "fbclid", "_ga"})
    FINGERPRINT_JS:str="""() => {
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

    OUTPUT_PATH: str | None = r"output/ui_flow.json"
    SCREENSHOT_DIR_PATH: str | None = r"output/screenshots"
    PRETTY_PRINT: bool = True

    PAGE_CONTENT_JS:str="""
                        () => {
                        // all visible text in main content area
                        const mainEl = document.querySelector('main, [role="main"], article') || document.body;
                        const fullText = mainEl.innerText?.trim().slice(0, 2000) || '';

                        // all buttons and their labels
                        const buttons = Array.from(document.querySelectorAll('button, [role="button"]'))
                        .filter(e => e.innerText?.trim())
                        .map(e => e.innerText.trim().slice(0, 50))
                        .slice(0, 20);

                        // all headings
                        const headings = Array.from(document.querySelectorAll('h1,h2,h3'))
                        .map(e => e.innerText.trim())
                        .filter(Boolean)
                        .slice(0, 10);

                        // all form labels
                        const formLabels = Array.from(document.querySelectorAll('label, input[placeholder]'))
                        .map(e => e.innerText?.trim() || e.getAttribute('placeholder') || '')
                        .filter(Boolean)
                        .slice(0, 15);

                        // all visible links text
                        const links = Array.from(document.querySelectorAll('a[href]'))
                        .filter(e => e.innerText?.trim())
                        .map(e => e.innerText.trim().slice(0, 50))
                        .slice(0, 20);

                        return { fullText, buttons, headings, formLabels, links };
                        }
                        """
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"



settings=Config()

