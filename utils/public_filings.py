"""Public filing discovery and contact extraction utilities.

This module provides a small helper class for locating public filings such
as Form 5500 documents and extracting officer contact information from them.
Remote database access is rate limited and responses are cached to avoid
excessive requests.

Example usage::

    filing_finder = PublicFilingsFinder()
    filings = filing_finder.find_filings(ein="123456789", org_name="Example Trust Fund")
    contacts = filing_finder.extract_contacts(filings, ["General Counsel", "CFO"])
"""

from __future__ import annotations

import io
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Pattern

try:
    import pdfplumber  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pdfplumber = None

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover - fallback for minimal envs
    requests = None
from .rate_limiting import exponential_backoff

logger = logging.getLogger(__name__)


@dataclass
class Filing:
    """Representation of a single filing record."""

    ein: str
    organization_name: str
    year: int
    form_type: str
    url: Optional[str] = None
    local_path: Optional[Path] = None
    content: Optional[bytes] = None


@dataclass
class ContactInfo:
    """Extracted officer contact information."""

    name: str
    title: str
    email: Optional[str] = None
    phone: Optional[str] = None
    confidence: float = 0.0


class PublicFilingsFinder:
    """Locate and parse public filings for union trust organizations."""

    def __init__(self, *, rate_limit: float = 1.0, local_dir: Path | None = None) -> None:
        self.rate_limit = rate_limit
        self._last_request = 0.0
        self.local_dir = local_dir
        if requests:
            self.session = requests.Session()
        else:  # pragma: no cover - fallback
            self.session = None
        self._cache: Dict[str, bytes] = {}

    # ------------------------------------------------------------------
    # Networking helpers
    # ------------------------------------------------------------------
    def _sleep_if_needed(self) -> None:
        now = time.time()
        elapsed = now - self._last_request
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request = time.time()

    @exponential_backoff
    def _fetch(self, url: str) -> bytes:
        if url in self._cache:
            return self._cache[url]
        self._sleep_if_needed()
        if self.session:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.content
        else:  # pragma: no cover - fallback
            from urllib import request as urlrequest

            with urlrequest.urlopen(url) as resp:  # type: ignore[call-arg]
                data = resp.read()
        self._cache[url] = data
        return data

    def _load_local(self, path: Path) -> bytes:
        key = str(path)
        if key in self._cache:
            return self._cache[key]
        data = path.read_bytes()
        self._cache[key] = data
        return data

    # ------------------------------------------------------------------
    # Search helpers
    # ------------------------------------------------------------------
    def find_filings(
        self, *, ein: str | None = None, org_name: str | None = None, year: int | None = None
    ) -> List[Filing]:
        """Search for filings matching criteria."""

        filings: List[Filing] = []
        if self.local_dir:
            for file in self.local_dir.glob("*.json"):
                data = json.loads(file.read_text())
                if ein and data.get("ein") != ein:
                    continue
                if org_name and org_name.lower() not in data.get("organization_name", "").lower():
                    continue
                if year and int(data.get("year", 0)) != year:
                    continue
                filings.append(
                    Filing(
                        ein=str(data.get("ein")),
                        organization_name=data.get("organization_name", ""),
                        year=int(data.get("year", 0)),
                        form_type=data.get("form_type", ""),
                        local_path=file,
                    )
                )
        else:  # pragma: no cover - placeholder for real API access
            query = {}
            if ein:
                query["ein"] = ein
            if org_name:
                query["name"] = org_name
            if year:
                query["year"] = str(year)
            url = "https://example.com/search"  # Placeholder
            logger.info("Querying %s with %s", url, query)
            resp = self._fetch(url)
            try:
                results = json.loads(resp)
            except json.JSONDecodeError:
                return []
            for item in results.get("filings", []):
                filings.append(
                    Filing(
                        ein=str(item.get("ein")),
                        organization_name=item.get("organization_name", ""),
                        year=int(item.get("year", 0)),
                        form_type=item.get("form_type", ""),
                        url=item.get("url"),
                    )
                )
        filings.sort(key=lambda f: f.year, reverse=True)
        return filings

    # ------------------------------------------------------------------
    # Parsing logic
    # ------------------------------------------------------------------
    def _parse_pdf(self, content: bytes, pattern: Pattern[str]) -> List[ContactInfo]:
        if not pdfplumber:  # pragma: no cover - optional dependency
            logger.warning("pdfplumber not available; skipping PDF parse")
            return []
        contacts: List[ContactInfo] = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        contacts.extend(self._extract_from_text(text, pattern))
        return contacts

    def _parse_html(self, html: str, pattern: Pattern[str]) -> List[ContactInfo]:
        return self._extract_from_text(html, pattern)

    def _parse_structured_data(
        self, data: Dict[str, object], pattern: Pattern[str], year: int
    ) -> List[ContactInfo]:
        contacts: List[ContactInfo] = []
        officers = data.get("officers")
        if isinstance(officers, list):
            for officer in officers:
                if not isinstance(officer, dict):
                    continue
                title = str(officer.get("title", ""))
                if not pattern.search(title.lower()):
                    continue
                info = ContactInfo(
                    name=str(officer.get("name", "")),
                    title=title,
                    email=officer.get("email"),
                    phone=officer.get("phone"),
                )
                info.confidence = self._score_contact(year, title, info)
                contacts.append(info)
        return contacts

    # ------------------------------------------------------------------
    def extract_contacts(self, filings: Iterable[Filing], target_roles: Iterable[str]) -> List[ContactInfo]:
        pattern = re.compile("|".join(re.escape(r.lower()) for r in target_roles))
        contacts: List[ContactInfo] = []
        for filing in filings:
            year = filing.year
            content = filing.content
            if content is None:
                if filing.local_path:
                    content = self._load_local(filing.local_path)
                elif filing.url:
                    content = self._fetch(filing.url)
                else:
                    continue
                filing.content = content
            if filing.local_path and filing.local_path.suffix == ".json":
                data = json.loads(content.decode("utf-8"))
                contacts.extend(self._parse_structured_data(data, pattern, year))
            elif filing.local_path and filing.local_path.suffix in {".html", ".htm"}:
                text = content.decode("utf-8", errors="ignore")
                parsed = self._parse_html(text, pattern)
                for c in parsed:
                    c.confidence = self._score_contact(year, c.title, c)
                contacts.extend(parsed)
            else:
                parsed = self._parse_pdf(content, pattern)
                for c in parsed:
                    c.confidence = self._score_contact(year, c.title, c)
                contacts.extend(parsed)
        return contacts

    # ------------------------------------------------------------------
    def _extract_from_text(self, text: str, pattern: Pattern[str]) -> List[ContactInfo]:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        results: List[ContactInfo] = []
        for idx, line in enumerate(lines):
            if pattern.search(line.lower()):
                name = lines[idx - 1] if idx > 0 else ""
                email = None
                phone = None
                if idx + 1 < len(lines) and "@" in lines[idx + 1]:
                    email = lines[idx + 1]
                if idx + 2 < len(lines) and re.search(r"\d{3}.*\d{4}", lines[idx + 2]):
                    phone = lines[idx + 2]
                results.append(ContactInfo(name=name, title=line, email=email, phone=phone))
        return results

    def _score_contact(self, year: int, title: str, info: ContactInfo) -> float:
        score = 0.5
        current_year = datetime.utcnow().year
        age = current_year - year
        if age <= 1:
            score += 0.3
        elif age <= 3:
            score += 0.1
        if info.email or info.phone:
            score += 0.1
        if title:
            score += 0.1
        return min(score, 1.0)

