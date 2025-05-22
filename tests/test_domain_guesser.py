import unittest

from utils.domain_guesser import DomainGuesser


class TestDomainGuesser(unittest.TestCase):
    def setUp(self) -> None:
        self.guesser = DomainGuesser()

    def test_generate_candidates(self) -> None:
        cands = self.guesser.generate_candidates("Example Fund")
        self.assertIn("examplefund.com", cands)
        self.assertIn("examplefund.org", cands)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
