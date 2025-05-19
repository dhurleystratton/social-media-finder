"""Small sample script using the LinkedIn contact discovery harness."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Adjust path so tests package can be imported when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.linkedin_contact_discovery import main


def run_sample() -> None:
    sample_csv = Path(__file__).with_name("sample_organizations.csv")
    output_csv = Path(tempfile.gettempdir()) / "executives_sample.csv"
    checkpoint = Path(tempfile.gettempdir()) / "checkpoint_sample.json"
    main([
        "--input",
        str(sample_csv),
        "--output",
        str(output_csv),
        "--limit",
        "5",
        "--checkpoint-file",
        str(checkpoint),
    ])


if __name__ == "__main__":  # pragma: no cover
    run_sample()
