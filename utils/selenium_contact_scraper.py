"""Selenium-based contact scraper for Taft-Hartley Union Trust websites."""

from __future__ import annotations

import csv
import json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

try:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.chrome.webdriver import WebDriver
except Exception:  # pragma: no cover - optional dependency
    By = None  # type: ignore
    Keys = None  # type: ignore
    WebDriver = object  # type: ignore

from .browser_utils import create_stealth_driver, human_scroll, clear_cookies
from .organization_processor import OrganizationProcessor, Organization
from .rate_limiting import exponential_backoff, SessionRotator

logger = logging.getLogger(__name__)


@dataclass
class ContactResult:
    """Structured executive contact information."""

    organization_name: str
    ein: int
    role: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    source: str
    confidence: float
    discovery_date: str


class SeleniumContactScraper:
    """Scrape executive contacts using Selenium with anti-detection measures."""

    SEARCH_URL = "https://www.bing.com"  # used when organization website missing
    LEADERSHIP_KEYWORDS = [
        "about",
        "leadership",
        "team",
        "staff",
        "management",
        "executives",
        "contact",
    ]

    def __init__(
        self,
        csv_path: str | Path,
        *,
        output_path: str | Path = "results.csv",
        checkpoint_path: str | Path = "scraper_checkpoint.json",
        batch_size: int = 10,
        headless: bool = True,
    ) -> None:
        self.processor = OrganizationProcessor(csv_path)
        self.output_path = Path(output_path)
        self.checkpoint_path = Path(checkpoint_path)
        self.batch_size = batch_size
        self.driver: Optional[WebDriver] = None
        self.rotator = SessionRotator(rotate_every=20)
        self.results: List[ContactResult] = []
        self._load_checkpoint()
        self.headless = headless

    # ------------------------------------------------------------------
    # Driver helpers
    # ------------------------------------------------------------------
    def _start_driver(self) -> None:
        if self.driver:
            return
        self.driver = create_stealth_driver(headless=self.headless)
        logger.debug("Selenium driver started")

    def _restart_driver(self) -> None:
        if self.driver:
            try:
                self.driver.quit()
            except Exception:  # noqa: BLE001
                pass
        self.driver = None
        self._start_driver()

    # ------------------------------------------------------------------
    def _load_checkpoint(self) -> None:
        if not self.checkpoint_path.exists():
            return
        data = json.loads(self.checkpoint_path.read_text())
        for item in data.get("results", []):
            self.results.append(ContactResult(**item))
        for ein in data.get("processed", []):
            self.processor.mark_processed(int(ein))
        logger.info("Loaded checkpoint with %d results", len(self.results))

    def _save_checkpoint(self) -> None:
        data = {
            "results": [r.__dict__ for r in self.results],
            "processed": [o.ein for o in self.processor.organizations.values() if o.processed],
        }
        tmp = self.checkpoint_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self.checkpoint_path)
        logger.debug("Checkpoint saved to %s", self.checkpoint_path)

    # ------------------------------------------------------------------
    # Scraping helpers
    # ------------------------------------------------------------------
    @exponential_backoff
    def _fetch_page(self, url: str) -> None:
        assert self.driver
        self.driver.get(url)
        human_scroll(self.driver)

    def _search_website(self, org: Organization) -> Optional[str]:
        """Search Bing for the organization's website."""
        assert self.driver
        query = f"{org.organization_name} {org.mail_us_city}"
        self._fetch_page(self.SEARCH_URL)
        try:
            box = self.driver.find_element(By.NAME, "q")
            box.clear()
            box.send_keys(query)
            box.send_keys(Keys.RETURN)
            time.sleep(random.uniform(2, 4))
            results = self.driver.find_elements(By.CSS_SELECTOR, "li.b_algo h2 a")
            if results:
                url = results[0].get_attribute("href")
                logger.debug("Search found website %s", url)
                return url
        except Exception as exc:  # noqa: BLE001
            logger.warning("Search failed for %s: %s", org.organization_name, exc)
        return None

    def _find_leadership_pages(self, base_url: str) -> List[str]:
        assert self.driver
        pages = []
        for kw in self.LEADERSHIP_KEYWORDS:
            url = base_url.rstrip("/") + "/" + kw
            try:
                self._fetch_page(url)
                html = self.driver.page_source
                if re.search(r"leadership|team|staff", html, re.I):
                    pages.append(url)
                    break
            except Exception:  # noqa: BLE001
                continue
        if not pages:
            pages.append(base_url)
        return pages

    def _parse_executives(self, html: str, target_roles: Iterable[str]) -> List[ContactResult]:
        text = re.sub(r"<[^>]+>", "\n", html)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        results: List[ContactResult] = []
        pattern = re.compile("|".join(re.escape(r.lower()) for r in target_roles))
        for idx, line in enumerate(lines):
            if pattern.search(line.lower()):
                name = lines[idx - 1] if idx > 0 else ""
                email = None
                phone = None
                if idx + 1 < len(lines) and "@" in lines[idx + 1]:
                    email = lines[idx + 1]
                results.append(
                    ContactResult(
                        organization_name="",
                        ein=0,
                        role=line,
                        name=name,
                        email=email,
                        phone=phone,
                        source="website",
                        confidence=0.7,
                        discovery_date=time.strftime("%Y-%m-%d"),
                    )
                )
        return results

    # ------------------------------------------------------------------
    def _process_org(self, org: Organization, target_roles: Iterable[str]) -> None:
        assert self.driver
        website = self._search_website(org)
        if not website:
            logger.info("No website found for %s", org.organization_name)
            return
        pages = self._find_leadership_pages(website)
        for page in pages:
            try:
                self._fetch_page(page)
            except Exception:  # noqa: BLE001
                continue
            html = self.driver.page_source
            contacts = self._parse_executives(html, target_roles)
            for c in contacts:
                c.organization_name = org.organization_name
                c.ein = org.ein
                self.results.append(c)

    # ------------------------------------------------------------------
    def run(self, *, target_roles: Iterable[str]) -> List[ContactResult]:
        self._start_driver()
        batch = self.processor.get_next_batch(size=self.batch_size)
        while batch:
            for org in batch:
                logger.info("Processing %s", org.organization_name)
                try:
                    self._process_org(org, target_roles)
                except Exception as exc:  # noqa: BLE001
                    logger.error("Error processing %s: %s", org.organization_name, exc)
                self.processor.mark_processed(org.ein)
                self._save_checkpoint()
                time.sleep(random.uniform(2, 5))
                if self.rotator.increment():
                    clear_cookies(self.driver)
                    self._restart_driver()
            batch = self.processor.get_next_batch(size=self.batch_size)
        if self.driver:
            self.driver.quit()
        self._write_results()
        return self.results

    # ------------------------------------------------------------------
    def _write_results(self) -> None:
        fieldnames = [
            "organization_name",
            "ein",
            "role",
            "name",
            "email",
            "phone",
            "source",
            "confidence",
            "discovery_date",
        ]
        write_header = not self.output_path.exists()
        with self.output_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            for r in self.results:
                writer.writerow(r.__dict__)
        logger.info("Wrote %d results to %s", len(self.results), self.output_path)


__all__ = ["SeleniumContactScraper", "ContactResult"]
