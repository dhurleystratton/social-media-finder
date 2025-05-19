"""Utility test framework for contact discovery components.

This module provides a lightweight testing harness that can
manage test samples, run component level checks, execute the
full discovery pipeline and export basic reports.
"""

from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .organization_processor import OrganizationProcessor, Organization
from .website_scraper import WebsiteScraper, OrgRecord
from .public_filings import PublicFilingsFinder
from .contact_identifier import ContactIdentifier
from .email_patterns import EmailPatternGenerator
from .contact_integration import ContactIntegration, ContactRecord

logger = logging.getLogger(__name__)


@dataclass
class Sample:
    """Representation of a test sample."""

    organizations: List[Organization]
    path: Optional[Path] = None


class TestFramework:
    """Coordinated testing for contact discovery components."""

    def __init__(self, *, full_dataset_path: str | Path, components: Dict[str, object], samples_dir: str | Path = "samples") -> None:
        self.dataset_path = Path(full_dataset_path)
        self.components = components
        self.processor = OrganizationProcessor(self.dataset_path)
        self.full_dataset = list(self.processor.organizations.values())
        self.samples_dir = Path(samples_dir)
        self.samples_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Sample management
    # ------------------------------------------------------------------
    def create_sample(
        self,
        *,
        size: int,
        random_seed: int | None = None,
        constraints: Dict[str, object] | None = None,
        eins: Iterable[int] | None = None,
        name: str | None = None,
    ) -> Sample:
        """Create and persist a sample from the dataset."""

        constraints = constraints or {}
        orgs = self.full_dataset
        if eins:
            ids = {int(e) for e in eins}
            orgs = [o for o in orgs if o.ein in ids]
        if constraints.get("min_plan_count"):
            minimum = int(constraints["min_plan_count"])
            orgs = [o for o in orgs if o.plan_count >= minimum]
        if constraints.get("has_phone_number"):
            orgs = [o for o in orgs if o.phone_num]
        if random_seed is not None:
            random.seed(random_seed)
        if size < len(orgs):
            orgs = random.sample(orgs, size)
        sample_name = name or f"sample_{size}_{random_seed if random_seed is not None else 'all'}"
        path = self.samples_dir / f"{sample_name}.json"
        data = [asdict(o) for o in orgs]
        path.write_text(json.dumps(data, indent=2))
        logger.info("Sample written to %s", path)
        return Sample(organizations=orgs, path=path)

    def load_sample(self, path: str | Path) -> Sample:
        """Load a previously saved sample."""

        p = Path(path)
        data = json.loads(p.read_text())
        orgs = [Organization(**item) for item in data]
        return Sample(organizations=orgs, path=p)

    # ------------------------------------------------------------------
    # Component tests
    # ------------------------------------------------------------------
    def test_components(self, *, sample: Sample, components: Iterable[str]) -> Dict[str, object]:
        """Run checks against individual components."""

        results: Dict[str, object] = {}
        for name in components:
            start = time.time()
            if name == "csv_processor":
                results[name] = [o.ein for o in sample.organizations]
            elif name == "website_scraper":
                scraper: WebsiteScraper = self.components[name]  # type: ignore[assignment]
                execs = []
                for org in sample.organizations:
                    execs.append(
                        scraper.find_executives(OrgRecord(name=org.organization_name, website=None), target_roles=["General Counsel"])
                    )
                results[name] = execs
            elif name == "filings_finder":
                finder: PublicFilingsFinder = self.components[name]  # type: ignore[assignment]
                contacts = []
                for org in sample.organizations:
                    filings = finder.find_filings(ein=str(org.ein))
                    contacts.append(finder.extract_contacts(filings, ["General Counsel"]))
                results[name] = contacts
            elif name == "contact_identifier":
                identifier: ContactIdentifier = self.components[name]  # type: ignore[assignment]
                contacts = [
                    {"name": "Jane Doe", "title": "Chief Financial Officer", "source": "website"}
                ]
                results[name] = identifier.categorize_contacts(contacts)
            elif name == "email_generator":
                gen: EmailPatternGenerator = self.components[name]  # type: ignore[assignment]
                emails = []
                for org in sample.organizations:
                    contact = {"name": "Jane Doe", "organization": org.organization_name, "website": "https://example.com"}
                    emails.append(gen.generate_candidates(contact))
                results[name] = emails
            elapsed = time.time() - start
            results[f"{name}_time"] = elapsed
        return results

    # ------------------------------------------------------------------
    # Pipeline test
    # ------------------------------------------------------------------
    def test_pipeline(self, *, sample: Sample, target_roles: Iterable[str]) -> List[ContactRecord]:
        """Run the full contact discovery pipeline on a sample."""

        integration = ContactIntegration(
            csv_processor=self.processor,
            website_scraper=self.components["website_scraper"],
            filings_finder=self.components["filings_finder"],
            linkedin_finder=self.components.get("linkedin_finder"),
        )
        all_contacts: Dict[str, ContactRecord] = {}
        for org in sample.organizations:
            contacts = []
            contacts.extend(integration._from_website(org, target_roles))
            contacts.extend(integration._from_filings(org, target_roles))
            contacts.extend(integration._from_database(org, target_roles))
            contacts.extend(integration._from_linkedin(org, target_roles))
            for c in contacts:
                integration._merge_contacts(all_contacts, c)
        return list(all_contacts.values())

    # ------------------------------------------------------------------
    # Reporting helpers
    # ------------------------------------------------------------------
    def generate_report(self, *, component_results: Dict[str, object], pipeline_results: List[ContactRecord], output_path: str | Path) -> None:
        """Write a simple HTML report summarizing results."""

        path = Path(output_path)
        parts = ["<html><body>", "<h1>Test Report</h1>"]
        parts.append("<h2>Component Results</h2><pre>")
        parts.append(json.dumps(component_results, indent=2))
        parts.append("</pre>")
        parts.append("<h2>Pipeline Results</h2><pre>")
        parts.append(json.dumps([asdict(r) for r in pipeline_results], indent=2))
        parts.append("</pre></body></html>")
        path.write_text("\n".join(parts), encoding="utf-8")
        logger.info("Report written to %s", path)

    # ------------------------------------------------------------------
    # Verification helpers
    # ------------------------------------------------------------------
    def verify_results(self, *, discovered: List[ContactRecord], verified: Iterable[Dict[str, str]]) -> Dict[str, object]:
        """Compare discovered contacts with verified ground truth."""

        disc_set = {(r.name.lower(), r.title.lower()) for r in discovered}
        ver_set = {(v["name"].lower(), v["title"].lower()) for v in verified}
        true_pos = disc_set & ver_set
        precision = len(true_pos) / len(disc_set) if disc_set else 0.0
        recall = len(true_pos) / len(ver_set) if ver_set else 0.0
        return {
            "precision": precision,
            "recall": recall,
            "missing": list(ver_set - disc_set),
            "extra": list(disc_set - ver_set),
        }

__all__ = ["TestFramework", "Sample"]
