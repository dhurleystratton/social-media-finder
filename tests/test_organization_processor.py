import unittest
from pathlib import Path

from utils import OrganizationProcessor, normalize_name


class TestOrganizationProcessor(unittest.TestCase):
    def test_normalize_name(self) -> None:
        self.assertEqual(normalize_name("Trust A, Inc."), "trust a inc")

    def test_batch_processing(self) -> None:
        sample_csv = Path(__file__).with_name("sample_taft_hartley.csv")
        processor = OrganizationProcessor(sample_csv)

        batch = processor.get_next_batch(size=1)
        self.assertEqual(len(batch), 1)
        first = batch[0]
        self.assertEqual(first.ein, 123456789)

        processor.mark_processed(first.ein)
        batch2 = processor.get_next_batch(size=2)
        self.assertEqual(len(batch2), 1)
        self.assertEqual(batch2[0].ein, 987654321)


if __name__ == "__main__":
    unittest.main()
