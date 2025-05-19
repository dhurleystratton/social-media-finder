import unittest
from pathlib import Path

from utils.public_filings import PublicFilingsFinder


class TestPublicFilingsFinder(unittest.TestCase):
    def setUp(self) -> None:
        self.finder = PublicFilingsFinder(local_dir=Path(__file__).parent)

    def test_find_and_extract_contacts(self) -> None:
        filings = self.finder.find_filings(ein="123456789")
        self.assertEqual(len(filings), 1)
        contacts = self.finder.extract_contacts(filings, ["General Counsel"])
        self.assertEqual(len(contacts), 1)
        contact = contacts[0]
        self.assertEqual(contact.name, "Alice Johnson")
        self.assertEqual(contact.title, "General Counsel")
        self.assertGreater(contact.confidence, 0.5)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
