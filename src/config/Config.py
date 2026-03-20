from pydantic import BaseModel
from .settings import settings

class Config(BaseModel):

    #llm config
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_API_VERSION: str
    AZURE_DEPLOYMENT_NAME: str
    LLM_ENRICH:bool=True
    CHAR_LIMIT:int=100_000 * 4 # 400k tokens
    SYSTEM_PROMPT:str="""
                        You are a UX analyst. Given a JSON description of a UI screen,
                        return a JSON object with:
                        - "name": a short, clear screen name (≤5 words, Title Case)
                        - "tags": list of relevant tags from: auth, home, settings, checkout, search,
                            help, onboarding, admin, form, list, detail, modal, error
                        - "heuristics": object mapping task names to difficulty scores 1-10
                        (10 = very hard to complete this task from this screen).
                        Use only tasks provided in the prompt.
                        Respond with ONLY valid JSON, no prose."""

    #crawl config
    CRAWL_URL: str="https://playwright.dev"
    MAX_DEPTH: int=99999
    MAX_NODES: int=99999
    STAY_ON_ORIGIN: bool = True

    #browser config
    BROWSER_HEADLESS:bool=True
    BROWSER_VIEWPORT:dict | None = field(default_factory=lambda: {"width": 1280, "height": 800})
    BROWSER_EXTRA_HEADERS:dict = field(default_factory=dict)

    #cookie config
    COOKIES:list[dict] = field(default_factory=list)

    #login details
    LOGIN_URL:str | None = None
        # list of {"selector": "...", "action": "fill|click", "value": "..."}
    LOGIN_STEPS: list[dict] = field(default_factory=list)
    LOGIN_USERNAME:str | None = None
    LOGIN_PASSWORD:str | None = None

    #action filtering
    SKIP_SELECTORS: list[str] = field(default_factory=lambda: [
        "[data-testid='logout']",
        "[href*='logout']",
        "[href*='signout']",
        "[href*='delete']",
        "[href*='remove']",
    ])
    # Only follow links matching these URL patterns (None = all)
    URL_ALLOWLIST_PATTERNS: list[str] = field(default_factory=list)
    NOISE_PARAMS:Set[str] = field(default_factory=lambda: {"utm_source", "utm_medium", "utm_campaign", "ref", "fbclid", "_ga"})
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



