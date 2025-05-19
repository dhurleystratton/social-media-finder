"""LinkedIn platform integration with anti-detection measures."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from selenium.webdriver.common.by import By

from utils.browser_utils import create_stealth_driver, human_scroll, clear_cookies
from utils.rate_limiting import linkedin_delay

logger = logging.getLogger(__name__)


class LinkedInFinder:
    """Browser-based LinkedIn profile finder.

    This implementation focuses on public information retrieval using Selenium
    with undetected-chromedriver. It incorporates randomized behaviour and
    conservative rate limiting to help avoid detection. Only publicly available
    data should be scraped with this tool.
    """

    def __init__(self, *, headless: bool = True, session_rotation: int = 5) -> None:
        self.headless = headless
        self.rotation_limit = session_rotation
        self._results_count = 0
        self.driver = create_stealth_driver(headless=headless)

    def _rotate_session(self) -> None:
        """Rotate the browser session after a number of operations."""
        logger.debug("Rotating browser session")
        try:
            self.driver.quit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error quitting driver during rotation: %s", exc)
        self.driver = create_stealth_driver(headless=self.headless)
        clear_cookies(self.driver)
        self._results_count = 0

    def _check_rotation(self) -> None:
        if self._results_count >= self.rotation_limit:
            self._rotate_session()

    def close(self) -> None:
        """Close the underlying driver."""
        try:
            self.driver.quit()
        except Exception:  # noqa: BLE001
            pass

    def search_profiles(self, query: str) -> List[Dict[str, Any]]:
        """Search LinkedIn for public profiles matching the query."""
        linkedin_delay()
        url = (
            "https://www.linkedin.com/search/results/people/?keywords="
            f"{quote_plus(query)}"
        )
        logger.debug("Navigating to %s", url)
        self.driver.get(url)
        human_scroll(self.driver)

        results: List[Dict[str, Any]] = []
        cards = self.driver.find_elements(By.CSS_SELECTOR, "a.app-aware-link")
        for card in cards:
            href = card.get_attribute("href")
            if href and "linkedin.com/in/" in href:
                results.append({"url": href})
            if len(results) >= 10:
                break
        self._results_count += 1
        self._check_rotation()
        return results

    def extract_public_info(self, profile_url: str) -> Dict[str, Optional[str]]:
        """Extract public information from a profile URL."""
        linkedin_delay()
        logger.debug("Fetching profile %s", profile_url)
        self.driver.get(profile_url)
        human_scroll(self.driver)
        info: Dict[str, Optional[str]] = {
            "name": None,
            "headline": None,
            "location": None,
        }
        try:
            info["name"] = self.driver.find_element(By.TAG_NAME, "h1").text
        except Exception:  # noqa: BLE001
            logger.debug("Name element not found")
        try:
            headline = self.driver.find_element(By.CSS_SELECTOR, "div.text-body-medium")
            info["headline"] = headline.text
        except Exception:  # noqa: BLE001
            logger.debug("Headline element not found")
        try:
            loc_elem = self.driver.find_element(By.CSS_SELECTOR, "span.text-body-small")
            info["location"] = loc_elem.text
        except Exception:  # noqa: BLE001
            logger.debug("Location element not found")
        self._results_count += 1
        self._check_rotation()
        return info

    def verify_profile(self, profile_url: str, expected_name: str) -> Dict[str, Any]:
        """Verify profile by comparing names and return a confidence score."""
        info = self.extract_public_info(profile_url)
        confidence = 0.0
        if info.get("name") and expected_name.lower() in info["name"].lower():
            confidence = 0.9
        return {"profile": info, "confidence": confidence}
