"""Contact integration for Taft-Hartley Union Trusts.

This module coordinates discovery of executive contact information from
multiple sources such as websites, public filings, industry databases,
and professional networks. Results are merged and scored to produce a
unified view of each contact.

Example
-------
>>> integration = ContactIntegration(
...     csv_processor=processor,
...     website_scraper=website_scraper,
...     filings_finder=filings_finder,
...     linkedin_finder=linkedin_finder,
... )
>>> integration.discover_contacts(
...     target_roles=["General Counsel", "CFO"],
...     batch_size=10,
...     min_confidence=0.6,
... )
>>> integration.export_results("discovered_contacts.xlsx")
"""

from __future__ import annotations

import csv
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Dict, Any

from .organization_processor import OrganizationProcessor, Organization
from .website_scraper import WebsiteScraper, OrgRecord
from .public_filings import PublicFilingsFinder
from .contact_identifier import normalize_title

logger = logging.getLogger(__name__)


@dataclass
class ContactRecord:
    """Aggregated contact information for an executive."""

    org_ein: int
    org_name: str
    name: str
    title: str
    sources: List[str] = field(default_factory=list)
    confidence: float = 0.0
    email: Optional[str] = None
    phone: Optional[str] = None


class ContactIntegration:
    """Coordinator for multi-source contact discovery."""

    SOURCE_WEIGHTS = {
        "website": 1.0,
        "filing": 0.9,
        "database": 0.8,
        "linkedin": 0.7,
    }

    def __init__(
        self,
        *,
        csv_processor: OrganizationProcessor,
        website_scraper: WebsiteScraper,
        filings_finder: PublicFilingsFinder,
        linkedin_finder: Any,
        database_finder: Any | None = None,
        checkpoint_file: str | None = None,
    ) -> None:
        self.csv_processor = csv_processor
        self.website_scraper = website_scraper
        self.filings_finder = filings_finder
        self.linkedin_finder = linkedin_finder
        self.database_finder = database_finder
        self.checkpoint_file = Path(checkpoint_file) if checkpoint_file else None
        self.results: List[ContactRecord] = []
        self._processed: set[int] = set()
        if self.checkpoint_file and self.checkpoint_file.exists():
            self._load_checkpoint()

    # ------------------------------------------------------------------
    # Checkpoint helpers
    # ------------------------------------------------------------------
    def _load_checkpoint(self) -> None:
        logger.info("Loading checkpoint from %s", self.checkpoint_file)
        data = json.loads(self.checkpoint_file.read_text())
        for r in data.get("results", []):
            self.results.append(ContactRecord(**r))
        self._processed = set(data.get("processed", []))

    def _save_checkpoint(self) -> None:
        if not self.checkpoint_file:
            return
        data = {
            "results": [r.__dict__ for r in self.results],
            "processed": sorted(self._processed),
        }
        tmp = self.checkpoint_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(tmp, self.checkpoint_file)
        logger.debug("Checkpoint saved to %s", self.checkpoint_file)

    # ------------------------------------------------------------------
    # Scoring and merge helpers
    # ------------------------------------------------------------------
    def _base_score(self, source: str, confidence: float) -> float:
        weight = self.SOURCE_WEIGHTS.get(source, 0.5)
        return weight * confidence

    @staticmethod
    def _normalize_name(name: str) -> str:
        return " ".join(name.lower().split())

    def _merge_contacts(self, contacts: Dict[str, ContactRecord], info: ContactRecord) -> None:
        key = f"{self._normalize_name(info.name)}|{normalize_title(info.title)}"
        existing = contacts.get(key)
        if existing:
            existing.confidence = min(1.0, existing.confidence + info.confidence * 0.5)
            if info.email and not existing.email:
                existing.email = info.email
            if info.phone and not existing.phone:
                existing.phone = info.phone
            for src in info.sources:
                if src not in existing.sources:
                    existing.sources.append(src)
        else:
            contacts[key] = info

    # ------------------------------------------------------------------
    # Source wrappers
    # ------------------------------------------------------------------
    def _from_website(self, org: Organization, roles: Iterable[str]) -> List[ContactRecord]:
        execs = self.website_scraper.find_executives(OrgRecord(name=org.organization_name, website=None), target_roles=roles)
        results: List[ContactRecord] = []
        for ex in execs:
            results.append(ContactRecord(
                org_ein=org.ein,
                org_name=org.organization_name,
                name=ex.name,
                title=ex.title,
                email=ex.email,
                confidence=self._base_score("website", ex.confidence),
                sources=["website"],
            ))
        return results

    def _from_filings(self, org: Organization, roles: Iterable[str]) -> List[ContactRecord]:
        filings = self.filings_finder.find_filings(ein=str(org.ein))
        contacts = self.filings_finder.extract_contacts(filings, roles)
        results: List[ContactRecord] = []
        for c in contacts:
            results.append(ContactRecord(
                org_ein=org.ein,
                org_name=org.organization_name,
                name=c.name,
                title=c.title,
                email=c.email,
                phone=c.phone,
                confidence=self._base_score("filing", c.confidence),
                sources=["filing"],
            ))
        return results

    def _from_database(self, org: Organization, roles: Iterable[str]) -> List[ContactRecord]:
        if not self.database_finder:
            return []
        results: List[ContactRecord] = []
        try:
            entries = self.database_finder.search(org, roles)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            logger.error("Database search failed: %s", exc)
            return []
        for e in entries:
            results.append(ContactRecord(
                org_ein=org.ein,
                org_name=org.organization_name,
                name=e.get("name", ""),
                title=e.get("title", ""),
                email=e.get("email"),
                phone=e.get("phone"),
                confidence=self._base_score("database", float(e.get("confidence", 0.5))),
                sources=["database"],
            ))
        return results

    def _from_linkedin(self, org: Organization, roles: Iterable[str]) -> List[ContactRecord]:
        results: List[ContactRecord] = []
        for role in roles:
            query = f"{org.organization_name} {role}"
            try:
                profiles = self.linkedin_finder.search_profiles(query)
            except Exception as exc:  # noqa: BLE001
                logger.error("LinkedIn search failed: %s", exc)
                continue
            for profile in profiles:
                url = profile.get("url")
                info = self.linkedin_finder.extract_public_info(url) if url else {}
                results.append(ContactRecord(
                    org_ein=org.ein,
                    org_name=org.organization_name,
                    name=info.get("name") or profile.get("name", ""),
                    title=info.get("headline") or role,
                    confidence=self._base_score("linkedin", 0.6),
                    sources=["linkedin"],
                ))
        return results

    # ------------------------------------------------------------------
    def discover_contacts(
        self,
        *,
        target_roles: Iterable[str],
        batch_size: int = 10,
        min_confidence: float = 0.6,
    ) -> List[ContactRecord]:
        """Process organizations and return discovered contacts."""

        all_contacts: Dict[str, ContactRecord] = {
            f"{self._normalize_name(r.name)}|{normalize_title(r.title)}": r
            for r in self.results
        }
        batch = self.csv_processor.get_next_batch(size=batch_size)
        while batch:
            for org in batch:
                if org.ein in self._processed:
                    continue
                logger.info("Processing EIN %s - %s", org.ein, org.organization_name)
                contacts = []
                contacts.extend(self._from_website(org, target_roles))
                contacts.extend(self._from_filings(org, target_roles))
                contacts.extend(self._from_database(org, target_roles))
                contacts.extend(self._from_linkedin(org, target_roles))
                for c in contacts:
                    self._merge_contacts(all_contacts, c)
                self.csv_processor.mark_processed(org.ein)
                self._processed.add(org.ein)
                self._save_checkpoint()
            batch = self.csv_processor.get_next_batch(size=batch_size)

        self.results = [r for r in all_contacts.values() if r.confidence >= min_confidence]
        return self.results

    # ------------------------------------------------------------------
    def export_results(self, path: str | Path) -> None:
        """Export results to JSON, CSV or Excel based on file extension."""

        path = Path(path)
        if path.suffix.lower() == ".json":
            with path.open("w", encoding="utf-8") as f:
                json.dump([r.__dict__ for r in self.results], f, indent=2)
        elif path.suffix.lower() == ".csv":
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "org_ein",
                        "org_name",
                        "name",
                        "title",
                        "email",
                        "phone",
                        "confidence",
                        "sources",
                    ],
                )
                writer.writeheader()
                for r in self.results:
                    row = r.__dict__.copy()
                    row["sources"] = ";".join(r.sources)
                    writer.writerow(row)
        elif path.suffix.lower() in {".xlsx", ".xls"}:
            try:
                from openpyxl import Workbook
            except Exception as exc:  # pragma: no cover - optional
                raise RuntimeError("Excel export requires openpyxl") from exc
            wb = Workbook()
            ws = wb.active
            ws.append([
                "org_ein",
                "org_name",
                "name",
                "title",
                "email",
                "phone",
                "confidence",
                "sources",
            ])
            for r in self.results:
                ws.append([
                    r.org_ein,
                    r.org_name,
                    r.name,
                    r.title,
                    r.email or "",
                    r.phone or "",
                    r.confidence,
                    ",".join(r.sources),
                ])
            wb.save(path)
        else:
            raise ValueError(f"Unsupported file type: {path.suffix}")


__all__ = ["ContactIntegration", "ContactRecord"]
