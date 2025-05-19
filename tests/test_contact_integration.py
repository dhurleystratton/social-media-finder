import unittest
from pathlib import Path

from utils import (
    OrganizationProcessor,
    ContactIntegration,
    WebsiteScraper,
    PublicFilingsFinder,
)


class StubWebsiteScraper(WebsiteScraper):
    def __init__(self) -> None:
        pass

    def find_executives(self, org: object, *, target_roles: list[str]) -> list[object]:
        return [
            type(
                "Exec",
                (),
                {"name": "Alice Johnson", "title": target_roles[0], "email": None, "confidence": 0.9},
            )()
        ]


class StubFilingsFinder(PublicFilingsFinder):
    def __init__(self) -> None:
        pass

    def find_filings(self, *, ein: str | None = None, org_name: str | None = None, year: int | None = None):
        return []

    def extract_contacts(self, filings, target_roles):
        return [
            type(
                "Contact",
                (),
                {
                    "name": "Alice Johnson",
                    "title": target_roles[0],
                    "email": "alice@example.com",
                    "phone": None,
                    "confidence": 0.8,
                },
            )()
        ]


class StubLinkedInFinder:
    def search_profiles(self, query: str):
        return [{"url": "https://linkedin.com/in/alice"}]

    def extract_public_info(self, url: str):
        return {"name": "Alice Johnson", "headline": "General Counsel"}


def load_processor() -> OrganizationProcessor:
    csv_path = Path(__file__).with_name("sample_taft_hartley.csv")
    return OrganizationProcessor(csv_path)


class TestContactIntegration(unittest.TestCase):
    def test_integration_dedup(self) -> None:
        processor = load_processor()
        integration = ContactIntegration(
            csv_processor=processor,
            website_scraper=StubWebsiteScraper(),
            filings_finder=StubFilingsFinder(),
            linkedin_finder=StubLinkedInFinder(),
        )
        results = integration.discover_contacts(target_roles=["General Counsel"], batch_size=1, min_confidence=0)
        self.assertEqual(len(results), 1)
        rec = results[0]
        self.assertEqual(rec.name, "Alice Johnson")
        self.assertIn("website", rec.sources)
        self.assertIn("filing", rec.sources)
        self.assertIn("linkedin", rec.sources)
        self.assertEqual(rec.email, "alice@example.com")
        self.assertGreater(rec.confidence, 0.9)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
