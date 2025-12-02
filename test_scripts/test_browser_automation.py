"""
Test script for browser automation integration.
Tests the browser automation tools directly without going through the agent.
"""

import os
import sys
import json
import logging

# Add parent directory to path to import browser_utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from browser_utils import BrowserManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_amazon_search():
    """Test searching Amazon for laptops."""
    logger.info("=" * 80)
    logger.info("Test 1: Amazon Laptop Search")
    logger.info("=" * 80)

    try:
        manager = BrowserManager()
        # Search Amazon for laptops
        result = manager.search_web(
            url="https://www.amazon.com",
            search_query="laptop",
            search_selector="input#twotabsearchtextbox",
            wait_selector="div.s-main-slot",
            take_screenshot=True,
        )

        logger.info(f"\nSuccess: {result.success}")
        logger.info(f"Session ID: {result.session_id}")
        logger.info(f"Execution Time: {result.execution_time:.2f}s")

        if result.success:
            logger.info(f"\nOutput:\n{result.output}")

            if result.scraped_content:
                logger.info(f"\nScraped Content:")
                logger.info(f"  Title: {result.scraped_content.get('title')}")
                logger.info(f"  URL: {result.scraped_content.get('url')}")

            if result.screenshot_base64:
                # Save screenshot
                import base64
                screenshot_path = "amazon_search_test.png"
                with open(screenshot_path, "wb") as f:
                    f.write(base64.b64decode(result.screenshot_base64))
                logger.info(f"\n✅ Screenshot saved to: {screenshot_path}")
        else:
            logger.error(f"\n❌ Error: {result.error}")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()


def test_scrape_example():
    """Test scraping example.com."""
    logger.info("\n" + "=" * 80)
    logger.info("Test 2: Scrape Example.com")
    logger.info("=" * 80)

    try:
        manager = BrowserManager()
        result = manager.scrape_page(
            url="https://example.com",
            selectors=["h1", "p"],
            extract_text=True,
            extract_html=False,
        )

        logger.info(f"\nSuccess: {result.success}")
        logger.info(f"Execution Time: {result.execution_time:.2f}s")

        if result.success:
            logger.info(f"\nScraped Content:")
            logger.info(json.dumps(result.scraped_content, indent=2))
        else:
            logger.error(f"\n❌ Error: {result.error}")

    except Exception as e:
        logger.error(f"Test failed: {e}")


def test_screenshot():
    """Test taking a screenshot."""
    logger.info("\n" + "=" * 80)
    logger.info("Test 3: Screenshot Example.com")
    logger.info("=" * 80)

    try:
        manager = BrowserManager()
        result = manager.take_screenshot(
            url="https://example.com",
            full_page=True,
        )

        logger.info(f"\nSuccess: {result.success}")
        logger.info(f"Execution Time: {result.execution_time:.2f}s")

        if result.success:
            # Save screenshot
            import base64
            screenshot_path = "example_com_test.png"
            with open(screenshot_path, "wb") as f:
                f.write(base64.b64decode(result.screenshot_base64))
            logger.info(f"\n✅ Screenshot saved to: {screenshot_path}")
        else:
            logger.error(f"\n❌ Error: {result.error}")

    except Exception as e:
        logger.error(f"Test failed: {e}")


if __name__ == "__main__":
    logger.info("Starting Browser Automation Tests")
    logger.info("Make sure AWS credentials are configured (aws configure)\n")

    # Run tests
    test_amazon_search()
    test_scrape_example()
    test_screenshot()

    logger.info("\n" + "=" * 80)
    logger.info("All tests completed!")
    logger.info("=" * 80)
