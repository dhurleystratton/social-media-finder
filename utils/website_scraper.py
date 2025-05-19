"""Ethical website scraper for extracting executive information."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional
from urllib.parse import quote_plus, urljoin, urlparse

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover - fallback for minimal envs
    requests = None

from urllib import robotparser, request as urlrequest

logger = logging.getLogger(__name__)


@dataclass
class Executive:
    """Simple representation of an executive contact."""

    name: str
    title: str
    email: Optional[str] = None
    confidence: float = 0.0


@dataclass
class OrgRecord:
    """Input organization record."""

    name: str
    website: Optional[str] = None


class WebsiteScraper:
    """Scrape organization leadership pages with basic ethics safeguards."""

    DEFAULT_PATHS: List[str] = [
        "about",
        "about/leadership",
        "about-us",
        "leadership",
        "team",
        "management",
    ]

    def __init__(self, *, rate_limit: float = 5.0, user_agent: str | None = None) -> None:
        self.rate_limit = rate_limit
        self._last_request = 0.0
        self.user_agent = user_agent or "ContactDiscoveryBot/1.0 (+https://example.com/bot)"
        if requests:
            self.session = requests.Session()
            self.session.headers.update({"User-Agent": self.user_agent})
        else:  # pragma: no cover - fallback
            self.session = None

    # ------------------------------------------------------------------
    # Networking helpers
    # ------------------------------------------------------------------
    def _sleep_if_needed(self) -> None:
        """Respect configured rate limits between requests."""

        now = time.time()
        elapsed = now - self._last_request
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request = time.time()

    def _allowed(self, url: str) -> bool:
        """Check robots.txt to determine if scraping is allowed."""

        parsed = urlparse(url)
        robots_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")
        rp = robotparser.RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
            allowed = rp.can_fetch(self.user_agent, url)
        except Exception as exc:  # noqa: BLE001
            logger.info("robots.txt fetch failed for %s: %s", robots_url, exc)
            allowed = True
        return allowed

    def fetch(self, url: str) -> str:
        """Fetch a URL if allowed by robots.txt."""

        if not self._allowed(url):
            logger.warning("Blocked by robots.txt: %s", url)
            return ""
        self._sleep_if_needed()
        try:
            if requests:
                resp = self.session.get(url, timeout=10)
                if resp.status_code == 200:
                    return resp.text
                logger.warning("Non-200 status %s for %s", resp.status_code, url)
            else:  # pragma: no cover - fallback
                with urlrequest.urlopen(url) as resp:
                    return resp.read().decode("utf-8", errors="ignore")
        except Exception as exc:  # noqa: BLE001
            logger.error("Request error for %s: %s", url, exc)
        return ""

    # ------------------------------------------------------------------
    # Discovery helpers
    # ------------------------------------------------------------------
    def derive_website(self, org_name: str) -> Optional[str]:
        """Attempt to discover a website using DuckDuckGo search."""

        query = quote_plus(org_name)
        search_url = f"https://duckduckgo.com/html/?q={query}"
        html = self.fetch(search_url)
        if not html:
            return None
        match = re.search(r'class="result__a"[^>]*href="([^"]+)"', html)
        if match:
            href = match.group(1)
            if "uddg=" in href:
                href = href.split("uddg=")[-1]
            return href
        return None

    def _contains_leadership_keywords(self, html: str) -> bool:
        text = re.sub(r"<[^>]+>", " ", html)
        text = " ".join(text.split()).lower()
        keywords = ["leadership", "team", "executive", "management"]
        return any(k in text for k in keywords)

    def find_leadership_page(self, base_url: str) -> tuple[str, str] | tuple[None, None]:
        """Locate a page likely containing leadership information."""

        for path in self.DEFAULT_PATHS:
            url = urljoin(base_url, path)
            html = self.fetch(url)
            if html and self._contains_leadership_keywords(html):
                return url, html
        html = self.fetch(base_url)
        if html:
            return base_url, html
        return None, None

    # ------------------------------------------------------------------
    # Parsing logic
    # ------------------------------------------------------------------
    @staticmethod
    def parse_executives(html: str, target_roles: Iterable[str]) -> List[Executive]:
        """Extract executive information from HTML content."""

        text = re.sub(r"<[^>]+>", "\n", html)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        execs: List[Executive] = []
        roles_pattern = re.compile("|".join(re.escape(r.lower()) for r in target_roles))
        for idx, line in enumerate(lines):
            match = roles_pattern.search(line.lower())
            if match:
                title = line.strip()
                name = lines[idx - 1] if idx > 0 else ""
                email = None
                if idx + 1 < len(lines) and "@" in lines[idx + 1]:
                    email = lines[idx + 1]
                confidence = 0.8 if match else 0.5
                execs.append(Executive(name=name, title=title, email=email, confidence=confidence))
        return execs

    # ------------------------------------------------------------------
    def find_executives(self, org: OrgRecord, *, target_roles: Iterable[str]) -> List[Executive]:
        """High level helper to locate executives for an organization."""

        website = org.website or self.derive_website(org.name)
        if not website:
            return []
        _, html = self.find_leadership_page(website)
        if not html:
            return []
        executives = self.parse_executives(html, target_roles)
        for ex in executives:
            ex.confidence = min(ex.confidence + 0.1, 1.0)
        return executives
