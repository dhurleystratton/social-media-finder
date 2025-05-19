import unittest
from pathlib import Path
import tempfile

from utils import (
    OrganizationProcessor,
    ContactIdentifier,
    WebsiteScraper,
    PublicFilingsFinder,
    EmailPatternGenerator,
    TestFramework,
)


class StubWebsiteScraper(WebsiteScraper):
    def __init__(self) -> None:
        pass

    def find_executives(self, org: object, *, target_roles: list[str]):
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


class TestFrameworkBasics(unittest.TestCase):
    def setUp(self) -> None:
        csv_path = Path(__file__).with_name("sample_taft_hartley.csv")
        components = {
            "csv_processor": OrganizationProcessor(csv_path),
            "website_scraper": StubWebsiteScraper(),
            "filings_finder": StubFilingsFinder(),
            "contact_identifier": ContactIdentifier(),
            "email_generator": EmailPatternGenerator(rate_limit=0),
            "linkedin_finder": StubLinkedInFinder(),
        }
        self.tmpdir = Path(tempfile.gettempdir())
        self.framework = TestFramework(full_dataset_path=csv_path, components=components, samples_dir=self.tmpdir)

    def test_sample_creation(self) -> None:
        sample = self.framework.create_sample(size=1, random_seed=1)
        self.assertEqual(len(sample.organizations), 1)
        self.assertTrue(sample.path and sample.path.exists())
        loaded = self.framework.load_sample(sample.path)
        self.assertEqual(len(loaded.organizations), 1)

    def test_pipeline(self) -> None:
        sample = self.framework.create_sample(size=1, random_seed=1)
        results = self.framework.test_pipeline(sample=sample, target_roles=["General Counsel"])
        self.assertEqual(len(results), 1)
        rec = results[0]
        self.assertEqual(rec.name, "Alice Johnson")
        self.assertIn("website", rec.sources)
        self.assertIn("filing", rec.sources)
        self.assertIn("linkedin", rec.sources)
        self.assertEqual(rec.email, "alice@example.com")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
