"""Browser utilities with anti-detection helpers."""

from __future__ import annotations

import logging
import random
import time
from typing import Sequence

import undetected_chromedriver as uc
from selenium.webdriver import ChromeOptions, Chrome

logger = logging.getLogger(__name__)

# Simple list of user agents for rotation; extend with a more comprehensive set
# in production deployments.
USER_AGENTS: Sequence[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113 Safari/537.36",
]


def create_stealth_driver(*, headless: bool = True) -> Chrome:
    """Create a Chrome driver instance with basic fingerprint randomization."""
    options = ChromeOptions()
    ua = random.choice(USER_AGENTS)
    options.add_argument(f"--user-agent={ua}")
    if headless:
        options.add_argument("--headless=new")
    # Additional flags can be added to reduce fingerprinting vectors
    driver = uc.Chrome(options=options)
    logger.debug("Started Chrome with randomized user agent")
    return driver


def human_scroll(driver: Chrome, *, min_pause: float = 0.3, max_pause: float = 0.8) -> None:
    """Simulate human-like scrolling behavior."""
    scroll_height = driver.execute_script("return document.body.scrollHeight")
    current_height = 0
    while current_height < scroll_height:
        step = random.randint(200, 400)
        current_height += step
        driver.execute_script(f"window.scrollTo(0, {current_height});")
        time.sleep(random.uniform(min_pause, max_pause))


def clear_cookies(driver: Chrome) -> None:
    """Clear cookies for the current driver session."""
    try:
        driver.delete_all_cookies()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to clear cookies: %s", exc)
