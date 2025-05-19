import unittest

from utils.email_patterns import EmailPatternGenerator, EmailCandidate


class TestEmailPatternGenerator(unittest.TestCase):
    def setUp(self) -> None:
        self.gen = EmailPatternGenerator(rate_limit=0)

    def test_generate_candidates(self) -> None:
        contact = {"name": "Jane Smith", "organization": "Example Fund"}
        cands = self.gen.generate_candidates(contact)
        emails = [c.email for c in cands]
        self.assertIn("jane.smith@examplefund.com", emails)
        self.assertIn("jsmith@examplefund.com", emails)

    def test_verify_cache(self) -> None:
        calls = {"mx": 0}

        def fake_mx(domain: str) -> bool:
            calls["mx"] += 1
            return True

        self.gen._check_mx = fake_mx
        self.gen._smtp_check = lambda e: True
        candidates = [EmailCandidate("jane.smith@example.com", 0.5)]
        self.gen.verify_emails(candidates)
        self.gen.verify_emails(candidates)
        self.assertEqual(calls["mx"], 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
