from pydantic import BaseModel
from src.config.Config import logger

class CrawlState(BaseModel):
    node_id: str
    url: str
    title: str
    dom_hash: str
    screenshot_path: str | None = None
    meta: dict = field(default_factory=dict)
    
class QueueItem(BaseModel):
    source_node_id: str
    action: ActionItem
    depth: int




class UICrawler:
    def __init__(self, config: CrawlerConfig):
        self.cfg = config
        self.graph = GraphBuilder()
        self._visited_fingerprints: set[str] = set()
        self._queue: deque[QueueItem] = deque()
        self._node_counter = 0
        self._origin: str = ""

    # ── public entry point ──────────────────

    async def crawl(self) -> dict:
        async with async_playwright() as pw:
            browser = await self._launch_browser(pw)
            try:
                page = await browser.new_page()
                await self._setup_page(page)

                # optional login
                if self.cfg.login_url:
                    await self._do_login(page)

                # seed
                await page.goto(self.cfg.start_url, wait_until="networkidle", timeout=30_000)
                self._origin = urlparse(self.cfg.start_url).netloc
                start_node = await self._register_state(page, parent_id=None, action=None)
                self.graph.set_start(start_node.node_id)

                # BFS
                await self._bfs(page)

            finally:
                await browser.close()

        return self.graph.to_dict()

    # ── BFS ─────────────────────────────────

    async def _bfs(self, page: Page):
        while self._queue:
            item = self._queue.popleft()
            if item.depth > self.cfg.max_depth:
                continue

            logger.log(f"  → exploring '{item.action.label}' from node '{item.source_node_id}'","info")

            # Navigate back to the source node's URL first, then re-reach state
            source_url  = self.graph.get_node(item.source_node_id)["url"]
            try:
                await page.goto(source_url, wait_until="networkidle", timeout=20_000)
                # re-apply auth state if needed (cookies are persistent in context)
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.log(f"Could not return to source url {source_url}: {e}","warning")
                continue

            # capture before-state
            before_fp = await fingerprint_page(page)

            # perform action
            try:
                await self._execute_action(page, item.action)
            except Exception as e:
                logger.log(f"Action failed ({item.action.label}): {e}","warning")
                continue

            await asyncio.sleep(0.5)

            # capture after-state
            after_fp = await fingerprint_page(page)

            if after_fp == before_fp:
                logger.log("   no state change","debug")
                continue

            # check domain (don't leave the site)
            current_url = page.url
            if not self._same_origin(current_url):
                logger.log("   left origin → skip","debug")
                continue

            # register new (or existing) node
            new_node = await self._register_state(
                page,
                parent_id=item.source_node_id,
                action=item.action,
                depth=item.depth,
            )
            if new_node is None:
                # already fully explored
                continue

    # ── state registration ───────────────────

    async def _register_state(
        self,
        page: Page,
        parent_id: str | None,
        action: ActionItem | None,
        depth: int = 0,
    ) -> CrawlState | None:
        fp = await fingerprint_page(page)

        # deduplicate
        if fp in self._visited_fingerprints:
            if parent_id and action:
                # still add the edge even if we've been here before
                existing_id = self.graph.fingerprint_to_id(fp)
                if existing_id:
                    self.graph.add_edge(parent_id, existing_id, action)
            return None

        self._visited_fingerprints.add(fp)
        self._node_counter += 1
        node_id = self._make_node_id(page)

        # screenshot (optional)
        shot_path = None
        if self.cfg.screenshot_dir:
            import os
            os.makedirs(self.cfg.screenshot_dir, exist_ok=True)
            shot_path = f"{self.cfg.screenshot_dir}/{node_id}.png"
            await page.screenshot(path=shot_path, full_page=False)

        state = CrawlState(
            node_id=node_id,
            url=page.url,
            title=await page.title(),
            dom_hash=fp,
            screenshot_path=shot_path,
        )

        self.graph.add_node(state, fingerprint=fp)
        if parent_id and action:
            self.graph.add_edge(parent_id, node_id, action)

        logger.log(f"  ✦ new node '{node_id}'  ({page.url})","info")

        # enqueue actions from this state
        if depth < self.cfg.max_depth:
            actions = await extract_actions(page, self.cfg)
            for act in actions:
                self._queue.append(QueueItem(
                    source_node_id=node_id,
                    action=act,
                    depth=depth + 1,
                ))

        return state

    # ── action execution ─────────────────────

    async def _execute_action(self, page: Page, action: ActionItem):
        el = page.locator(action.selector).first
        tag = action.tag.lower()

        if tag in ("a", "button") or action.role in ("button", "link", "menuitem", "tab"):
            async with page.expect_navigation(timeout=8_000, wait_until="networkidle").and_then(
                lambda: None
            ) if action.likely_navigates else self._null_ctx():
                await el.click(timeout=5_000)
        elif tag == "select":
            options = await el.locator("option").all()
            if options:
                val = await options[1 if len(options) > 1 else 0].get_attribute("value")
                await el.select_option(val or "")
        elif tag == "input":
            input_type = action.input_type or "text"
            if input_type in ("text", "email", "search", "url", "tel"):
                await el.fill(self.cfg.dummy_text)
            elif input_type == "password":
                await el.fill(self.cfg.dummy_password)
            elif input_type in ("checkbox", "radio"):
                await el.check()
        else:
            await el.click(timeout=5_000)

        try:
            await page.wait_for_load_state("networkidle", timeout=5_000)
        except Exception:
            pass

    @staticmethod
    def _null_ctx():
        """Dummy async context manager for non-navigating actions."""
        class _Null:
            async def __aenter__(self): return self
            async def __aexit__(self, *_): pass
        return _Null()

    # ── helpers ──────────────────────────────

    async def _launch_browser(self, pw: Playwright) -> Browser:
        return await pw.chromium.launch(headless=self.cfg.headless)

    async def _setup_page(self, page: Page):
        if self.cfg.viewport:
            await page.set_viewport_size(self.cfg.viewport)
        if self.cfg.extra_headers:
            await page.set_extra_http_headers(self.cfg.extra_headers)
        if self.cfg.cookies:
            await page.context.add_cookies(self.cfg.cookies)

    async def _do_login(self, page: Page):
        logger.log(f"Logging in via {self.cfg.login_url}","info")
        await page.goto(self.cfg.login_url, wait_until="networkidle", timeout=20_000)
        if self.cfg.login_steps:
            for step in self.cfg.login_steps:
                sel = step["selector"]
                action = step["action"]
                value = step.get("value", "")
                el = page.locator(sel).first
                if action == "fill":
                    await el.fill(value)
                elif action == "click":
                    await el.click()
                await asyncio.sleep(0.4)
        await page.wait_for_load_state("networkidle", timeout=15_000)
        logger.log(f"Login complete. Current URL: {page.url}","info")

    def _make_node_id(self, page: Page) -> str:
        path = urlparse(page.url).path.strip("/").replace("/", "_") or "root"
        path = re.sub(r"[^a-zA-Z0-9_]", "_", path)
        return f"{path}_{self._node_counter}" if path else f"screen_{self._node_counter}"

    def _same_origin(self, url: str) -> bool:
        if not self.cfg.stay_on_origin:
            return True
        return urlparse(url).netloc == self._origin
