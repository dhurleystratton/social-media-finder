import unittest
from datetime import datetime, timedelta

from utils import ContactIdentifier


class TestContactIdentifier(unittest.TestCase):
    def setUp(self) -> None:
        self.identifier = ContactIdentifier()

    def test_basic_matching(self) -> None:
        contacts = [
            {"name": "Jane Smith", "title": "Chief Legal Officer", "source": "website"},
            {"name": "John Doe", "title": "Finance Director", "source": "linkedin"},
        ]
        matched = self.identifier.categorize_contacts(contacts)
        roles = {m.role for m in matched}
        self.assertIn("General Counsel", roles)
        self.assertIn("CFO", roles)

    def test_conflict_resolution(self) -> None:
        recent = datetime.utcnow() - timedelta(days=100)
        contacts = [
            {"name": "A", "title": "Finance Director", "source": "linkedin"},
            {"name": "B", "title": "Chief Financial Officer", "source": "website", "updated_at": recent},
        ]
        matched = self.identifier.categorize_contacts(contacts)
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0].name, "B")
        self.assertEqual(matched[0].role, "CFO")
        self.assertGreater(matched[0].score, 0.5)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
