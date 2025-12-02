"""In process MCP server for Browser Automation."""

from browser_utils import BrowserManager
from claude_agent_sdk import tool, create_sdk_mcp_server
from typing import Any
import json
import logging

logger = logging.getLogger(__name__)

# Initialize the browser manager
browser_manager = BrowserManager()


@tool(
    "search_web",
    "Navigate to a URL and perform web search. Can fill forms, submit searches, and extract results.",
    {
        "url": str,
        "search_query": str,
        "search_selector": str,
        "submit_button": str,
        "wait_selector": str,
        "take_screenshot": bool,
    },
)
async def search_web(args: dict[str, Any]) -> dict[str, Any]:
    """
    Search the web by navigating to a URL and filling in search forms.

    Example:
        url: "https://www.amazon.com"
        search_query: "laptop"
        search_selector: "input#twotabsearchtextbox"
        wait_selector: "div.s-main-slot"
        take_screenshot: True
    """
    result = await browser_manager.search_web(
        url=args.get("url"),
        search_query=args.get("search_query"),
        search_selector=args.get("search_selector"),
        submit_button=args.get("submit_button"),
        wait_selector=args.get("wait_selector"),
        take_screenshot=args.get("take_screenshot", False),
    )
    return {"content": [{"type": "text", "text": result.model_dump_json(indent=2)}]}


@tool(
    "scrape_page",
    "Scrape content from a web page. Extract text, HTML, or specific elements using CSS selectors.",
    {
        "url": str,
        "selectors": list,
        "extract_text": bool,
        "extract_html": bool,
    },
)
async def scrape_page(args: dict[str, Any]) -> dict[str, Any]:
    """
    Scrape content from a web page.

    Example:
        url: "https://example.com"
        selectors: ["h1", ".price", "#description"]
        extract_text: True
        extract_html: False
    """
    selectors = args.get("selectors")
    if isinstance(selectors, str):
        selectors = json.loads(selectors)

    result = await browser_manager.scrape_page(
        url=args.get("url"),
        selectors=selectors,
        extract_text=args.get("extract_text", True),
        extract_html=args.get("extract_html", False),
    )
    return {"content": [{"type": "text", "text": result.model_dump_json(indent=2)}]}


@tool(
    "take_screenshot",
    "Take a screenshot of a web page. Can capture full page or specific elements.",
    {
        "url": str,
        "full_page": bool,
        "selector": str,
    },
)
async def take_screenshot(args: dict[str, Any]) -> dict[str, Any]:
    """
    Take a screenshot of a web page.

    Example:
        url: "https://example.com"
        full_page: True
        selector: "#main-content"
    """
    result = await browser_manager.take_screenshot(
        url=args.get("url"),
        full_page=args.get("full_page", False),
        selector=args.get("selector"),
    )
    return {"content": [{"type": "text", "text": result.model_dump_json(indent=2)}]}


browser_mcp_server = create_sdk_mcp_server(
    name="browser",
    version="1.0.0",
    tools=[search_web, scrape_page, take_screenshot],
)
