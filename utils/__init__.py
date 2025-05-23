"""Utility package for social media finder."""

from .organization_processor import OrganizationProcessor, Organization, normalize_name
from .website_scraper import WebsiteScraper, OrgRecord, Executive
try:
    from .selenium_contact_scraper import SeleniumContactScraper, ContactResult
except Exception:  # pragma: no cover - optional dependency
    SeleniumContactScraper = None  # type: ignore
    ContactResult = None  # type: ignore
from .public_filings import PublicFilingsFinder, Filing, ContactInfo
from .contact_identifier import ContactIdentifier, MatchedContact, Contact
from .contact_integration import ContactIntegration, ContactRecord
from .email_patterns import EmailPatternGenerator, EmailCandidate
from .test_framework import TestFramework, Sample

__all__ = [
    "OrganizationProcessor",
    "Organization",
    "normalize_name",
    "WebsiteScraper",
    "OrgRecord",
    "Executive",
    "SeleniumContactScraper",
    "ContactResult",
    "PublicFilingsFinder",
    "Filing",
    "ContactInfo",
    "ContactIdentifier",
    "MatchedContact",
    "Contact",
    "ContactIntegration",
    "ContactRecord",
    "EmailPatternGenerator",
    "EmailCandidate",
    "TestFramework",
    "Sample",
]

