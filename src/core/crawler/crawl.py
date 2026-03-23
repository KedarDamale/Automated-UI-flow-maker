from pydantic import BaseModel, Field
from src.config.Logger import logger
from src.core.graph_builder.graph import GraphBuilder
from src.config.Config import settings
from src.core.page_action_extraction.extractor import ActionItem, extract_actions
from playwright.async_api import async_playwright, Browser, Page, Playwright
from collections import deque
from urllib.parse import urlparse
from src.core.fingerprinting.fingerprint_page import fingerprint_page
import re
import asyncio


class CrawlState(BaseModel):
    node_id: str
    url: str
    title: str
    dom_hash: str
    screenshot_path: str | None = None
    meta: dict = Field(default_factory=dict)


class QueueItem(BaseModel):
    source_node_id: str
    action: ActionItem
    depth: int


class UICrawler:
    def __init__(self):
        self.settings = settings
        self.graph = GraphBuilder()
        self._visited_fingerprints: set[str] = set()
        self._queue: deque[QueueItem] = deque()
        self._node_counter = 0
        self._origin: str = ""

    async def crawl(self) -> dict:
        async with async_playwright() as pw:
            browser = await self._launch_browser(pw)
            try:
                page = await browser.new_page()
                await self._setup_page(page)

                if self.settings.LOGIN_URL:
                    await self._do_login(page)

                await page.goto(self.settings.CRAWL_URL, wait_until="networkidle", timeout=30_000)
                self._origin = urlparse(self.settings.CRAWL_URL).netloc
                start_node = await self._register_state(page, parent_id=None, action=None)
                self.graph.set_start(start_node.node_id)

                await self._bfs(page)

            finally:
                await browser.close()

        return self.graph.to_dict()

    async def _bfs(self, page: Page):
        while self._queue:
            item = self._queue.popleft()
            if item.depth > self.settings.MAX_DEPTH:
                continue

            logger.log(f"  → exploring '{item.action.label}' from node '{item.source_node_id}'", "info")

            source_url = self.graph.get_node(item.source_node_id)["url"]
            try:
                await page.goto(source_url, wait_until="networkidle", timeout=20_000)
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.log(f"Could not return to source url {source_url}: {e}", "warning")
                continue

            before_fp = await fingerprint_page(page)

            try:
                await self._execute_action(page, item.action)
            except Exception as e:
                logger.log(f"Action failed ({item.action.label}): {e}", "warning")
                continue

            await asyncio.sleep(1.0)
            try:
                await page.wait_for_load_state("networkidle", timeout=8_000)
            except Exception:
                pass

            logger.log(f"After action URL: {page.url}", "debug")

            after_fp = await fingerprint_page(page)

            if after_fp == before_fp:
                logger.log("no state change", "debug")
                continue

            current_url = page.url
            if not self._same_origin(current_url):
                logger.log(f"left origin → skip ({current_url})", "debug")
                continue

            new_node = await self._register_state(
                page,
                parent_id=item.source_node_id,
                action=item.action,
                depth=item.depth,
            )
            if new_node is None:
                continue

    async def _register_state(
        self,
        page: Page,
        parent_id: str | None,
        action: ActionItem | None,
        depth: int = 0,
    ) -> CrawlState | None:
        fp = await fingerprint_page(page)

        if fp in self._visited_fingerprints:
            if parent_id and action:
                existing_id = self.graph.fingerprint_to_id(fp)
                if existing_id:
                    self.graph.add_edge(parent_id, existing_id, action)
            return None

        self._visited_fingerprints.add(fp)
        self._node_counter += 1
        node_id = self._make_node_id(page)

        shot_path = None
        if self.settings.SCREENSHOT_DIR_PATH:
            import os
            os.makedirs(self.settings.SCREENSHOT_DIR_PATH, exist_ok=True)
            shot_path = f"{self.settings.SCREENSHOT_DIR_PATH}/{node_id}.png"
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

        logger.log(f"  ✦ new node '{node_id}'  ({page.url})", "info")

        if depth < self.settings.MAX_DEPTH:
            actions = await extract_actions(page, self.settings)
            for act in actions:
                self._queue.append(QueueItem(
                    source_node_id=node_id,
                    action=act,
                    depth=depth + 1,
                ))

        return state

    async def _execute_action(self, page: Page, action: ActionItem):
        el = page.locator(action.selector).first
        tag = action.tag.lower()

        if tag == "select":
            options = await el.locator("option").all()
            if options:
                val = await options[1 if len(options) > 1 else 0].get_attribute("value")
                await el.select_option(val or "")
        elif tag == "input":
            input_type = action.input_type or "text"
            if input_type in ("text", "email", "search", "url", "tel"):
                await el.fill(self.settings.DUMMY_TEXT)
            elif input_type == "password":
                await el.fill(self.settings.DUMMY_PASSWORD)
            elif input_type in ("checkbox", "radio"):
                await el.check()
        else:
            await el.click(timeout=5_000)

    async def _launch_browser(self, pw: Playwright) -> Browser:
        return await pw.chromium.launch(headless=self.settings.BROWSER_HEADLESS)

    async def _setup_page(self, page: Page):
        if self.settings.BROWSER_VIEWPORT:
            await page.set_viewport_size(self.settings.BROWSER_VIEWPORT)
        if self.settings.BROWSER_EXTRA_HEADERS:
            await page.set_extra_http_headers(self.settings.BROWSER_EXTRA_HEADERS)
        if self.settings.COOKIES:
            await page.context.add_cookies(self.settings.COOKIES)

    async def _do_login(self, page: Page):
        logger.log(f"Logging in via {self.settings.LOGIN_URL}", "info")
        await page.goto(self.settings.LOGIN_URL, wait_until="networkidle", timeout=20_000)
        if self.settings.LOGIN_STEPS:
            for step in self.settings.LOGIN_STEPS:
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
        logger.log(f"Login complete. Current URL: {page.url}", "info")

    def _make_node_id(self, page: Page) -> str:
        path = urlparse(page.url).path.strip("/").replace("/", "_") or "root"
        path = re.sub(r"[^a-zA-Z0-9_]", "_", path)
        return f"{path}_{self._node_counter}" if path else f"screen_{self._node_counter}"

    def _same_origin(self, url: str) -> bool:
        if not self.settings.STAY_ON_ORIGIN:
            return True
        return urlparse(url).netloc == self._origin