"""Browser utilities using bedrock_agentcore BrowserClient directly."""

import os
import base64
import logging
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from bedrock_agentcore.tools.browser_client import browser_session
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BrowserOperationResult(BaseModel):
    """Result model for browser operations."""
    success: bool
    session_id: Optional[str] = None
    execution_time: float = Field(..., ge=0)
    output: Optional[str] = None
    screenshot_base64: Optional[str] = None
    scraped_content: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BrowserManager:
    """Manages browser operations using AgentCore BrowserClient."""

    def __init__(self, region: str = "eu-central-1"):
        """
        Initialize Browser Manager.

        Args:
            region: AWS region for AgentCore Browser (default: eu-central-1)
        """
        self.region = region or os.environ.get("AWS_REGION", "eu-central-1")

    @asynccontextmanager
    async def _get_browser_page(self):
        """
        Async context manager for browser session using AgentCore's browser_session.

        Yields:
            tuple: (page, session_id)
        """
        with browser_session(self.region) as client:
            ws_url, headers = client.generate_ws_headers()
            session_id = client.session_id

            async with async_playwright() as playwright:
                browser = await playwright.chromium.connect_over_cdp(ws_url, headers=headers)

                try:
                    # Get or create context and page
                    if browser.contexts:
                        context = browser.contexts[0]
                    else:
                        context = await browser.new_context()

                    if context.pages:
                        page = context.pages[0]
                    else:
                        page = await context.new_page()

                    yield page, session_id

                finally:
                    try:
                        await browser.close()
                    except Exception as e:
                        logger.warning(f"Error closing browser: {e}")

    async def navigate(
        self,
        url: str,
        wait_for: str = "domcontentloaded",
        timeout: int = 30000,
        take_screenshot: bool = False,
    ) -> BrowserOperationResult:
        """
        Navigate to a URL.

        Args:
            url: URL to navigate to
            wait_for: Wait condition (domcontentloaded, load, networkidle)
            timeout: Navigation timeout in milliseconds
            take_screenshot: Whether to capture screenshot
        """
        import time
        start_time = time.time()

        try:
            async with self._get_browser_page() as (page, session_id):
                logger.info(f"Navigating to {url}")
                await page.goto(url, wait_until=wait_for, timeout=timeout)

                title = await page.title()
                current_url = page.url

                screenshot_b64 = None
                if take_screenshot:
                    screenshot_bytes = await page.screenshot(full_page=False)
                    screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

                execution_time = time.time() - start_time

                return BrowserOperationResult(
                    success=True,
                    session_id=session_id,
                    execution_time=execution_time,
                    output=f"Title: {title}\nURL: {current_url}",
                    screenshot_b64=screenshot_b64,
                    scraped_content={
                        "title": title,
                        "url": current_url,
                    },
                )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Navigation failed: {e}")
            return BrowserOperationResult(
                success=False,
                execution_time=execution_time,
                error=str(e),
            )

    async def search_web(
        self,
        url: str,
        search_query: Optional[str] = None,
        search_selector: Optional[str] = None,
        submit_button: Optional[str] = None,
        wait_selector: Optional[str] = None,
        take_screenshot: bool = False,
    ) -> BrowserOperationResult:
        """
        Navigate to URL and optionally perform a search.

        Args:
            url: URL to navigate to
            search_query: Text to search for
            search_selector: CSS selector for search input
            submit_button: CSS selector for submit button
            wait_selector: CSS selector to wait for after search
            take_screenshot: Whether to capture screenshot
        """
        import time
        start_time = time.time()

        try:
            async with self._get_browser_page() as (page, session_id):
                logger.info(f"Navigating to {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Perform search if query provided
                if search_query and search_selector:
                    logger.info(f"Searching for: {search_query}")
                    await page.fill(search_selector, search_query)

                    if submit_button:
                        await page.click(submit_button)
                    else:
                        await page.press(search_selector, "Enter")

                    # Wait for results
                    if wait_selector:
                        await page.wait_for_selector(wait_selector, timeout=10000)
                    else:
                        await page.wait_for_load_state("networkidle", timeout=10000)

                # Get page content
                content = await page.content()
                title = await page.title()
                current_url = page.url

                # Take screenshot if requested
                screenshot_b64 = None
                if take_screenshot:
                    screenshot_bytes = await page.screenshot(full_page=False)
                    screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

                execution_time = time.time() - start_time

                return BrowserOperationResult(
                    success=True,
                    session_id=session_id,
                    execution_time=execution_time,
                    output=f"Title: {title}\nURL: {current_url}\nContent length: {len(content)} chars",
                    screenshot_base64=screenshot_b64,
                    scraped_content={
                        "title": title,
                        "url": current_url,
                        "content": content[:5000],  # Truncate for size
                    },
                )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Search failed: {e}")
            return BrowserOperationResult(
                success=False,
                execution_time=execution_time,
                error=str(e),
            )

    async def scrape_page(
        self,
        url: Optional[str] = None,
        selectors: Optional[List[str]] = None,
        extract_text: bool = True,
        extract_html: bool = False,
    ) -> BrowserOperationResult:
        """
        Scrape content from a URL.

        Args:
            url: URL to navigate to
            selectors: List of CSS selectors to extract
            extract_text: Extract text content
            extract_html: Extract HTML content
        """
        import time
        start_time = time.time()

        try:
            async with self._get_browser_page() as (page, session_id):
                if not url:
                    return BrowserOperationResult(
                        success=False,
                        execution_time=time.time() - start_time,
                        error="URL is required for scraping",
                    )

                logger.info(f"Navigating to {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Extract content
                scraped_data = {
                    "url": page.url,
                    "title": await page.title(),
                }

                if extract_text:
                    scraped_data["text"] = await page.inner_text("body")

                if extract_html:
                    scraped_data["html"] = await page.content()

                # Extract specific elements if selectors provided
                if selectors:
                    elements = []
                    for selector in selectors:
                        try:
                            element_text = await page.locator(selector).all_text_contents()
                            elements.append({
                                "selector": selector,
                                "text": element_text,
                            })
                        except Exception as e:
                            logger.warning(f"Could not extract {selector}: {e}")
                            elements.append({
                                "selector": selector,
                                "error": str(e),
                            })

                    scraped_data["elements"] = elements

                execution_time = time.time() - start_time

                return BrowserOperationResult(
                    success=True,
                    session_id=session_id,
                    execution_time=execution_time,
                    output=f"Scraped {len(scraped_data)} fields from {page.url}",
                    scraped_content=scraped_data,
                )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Scraping failed: {e}")
            return BrowserOperationResult(
                success=False,
                execution_time=execution_time,
                error=str(e),
            )

    async def take_screenshot(
        self,
        url: str,
        full_page: bool = False,
        selector: Optional[str] = None,
    ) -> BrowserOperationResult:
        """
        Take a screenshot of a URL.

        Args:
            url: URL to navigate to
            full_page: Whether to capture full scrollable page
            selector: CSS selector of specific element to screenshot
        """
        import time
        start_time = time.time()

        try:
            async with self._get_browser_page() as (page, session_id):
                logger.info(f"Navigating to {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Take screenshot
                if selector:
                    element = page.locator(selector)
                    screenshot_bytes = await element.screenshot()
                else:
                    screenshot_bytes = await page.screenshot(full_page=full_page)

                screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

                execution_time = time.time() - start_time

                return BrowserOperationResult(
                    success=True,
                    session_id=session_id,
                    execution_time=execution_time,
                    output=f"Screenshot captured from {page.url}",
                    screenshot_base64=screenshot_b64,
                )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Screenshot failed: {e}")
            return BrowserOperationResult(
                success=False,
                execution_time=execution_time,
                error=str(e),
            )
