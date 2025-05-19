"""Utility package for social media finder."""

from .organization_processor import OrganizationProcessor, Organization, normalize_name
from .website_scraper import WebsiteScraper, OrgRecord, Executive
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

