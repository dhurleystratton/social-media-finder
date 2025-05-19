"""Test harness for LinkedIn contact discovery."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from platforms.linkedin import LinkedInFinder
from utils.rate_limiting import SessionRotator, linkedin_delay


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

TARGET_TITLES = [
    "General Counsel",
    "Deputy General Counsel",
    "Chief Financial Officer",
    "Head of Revenue Cycle",
    "Executive Director",
]


@dataclass
class ExecutiveResult:
    org_name: str
    exec_name: str
    title: str
    linkedin_url: str | None = None
    emails: List[str] = field(default_factory=list)
    confidence: int = 0
    method: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


def discover_linkedin_company(finder: LinkedInFinder, org_name: str) -> Optional[str]:
    """Discover the LinkedIn company page for the organization."""
    logger.info("Searching LinkedIn for company %s", org_name)
    linkedin_delay(120, 180)
    results = finder.search_profiles(org_name)
    for result in results:
        url = result.get("url")
        if url and "/company/" in url:
            logger.info("Found company page: %s", url)
            return url
    logger.warning("No LinkedIn company page found for %s", org_name)
    return None


def find_target_executives(
    finder: LinkedInFinder, company_url: str, target_titles: Iterable[str]
) -> List[Dict[str, str]]:
    """Locate executives that match desired titles."""
    logger.info("Finding executives on %s", company_url)
    linkedin_delay(120, 180)
    # Placeholder implementation: this would navigate the company page
    # and extract profiles matching the titles. For now we return an empty list.
    return []


def extract_contact_info(finder: LinkedInFinder, profile_url: str) -> Dict[str, str]:
    """Extract public contact info from a profile."""
    logger.info("Extracting info from %s", profile_url)
    linkedin_delay(120, 180)
    info = finder.extract_public_info(profile_url)
    return {
        "name": info.get("name") or "",
        "title": info.get("headline") or "",
    }


def predict_email_format(org_name: str, exec_name: str, website: str | None) -> List[str]:
    """Generate possible email addresses based on common patterns."""
    logger.info("Predicting email for %s at %s", exec_name, org_name)
    if not website:
        domain = "example.com"
    else:
        domain = website.split("//")[-1].split("/")[0]
    first, *rest = exec_name.split()
    last = rest[-1] if rest else ""
    emails = [
        f"{first.lower()}.{last.lower()}@{domain}",
        f"{first[0].lower()}{last.lower()}@{domain}",
    ]
    return emails


def calculate_confidence_score(result: ExecutiveResult) -> int:
    """Assign a simple confidence score."""
    score = 50
    if result.linkedin_url:
        score += 20
    if result.emails:
        score += 20
    if any(result.exec_name.lower().startswith(t.split()[0].lower()) for t in TARGET_TITLES):
        score += 10
    return min(score, 100)


def process_organization(finder: LinkedInFinder, org: Dict[str, str]) -> List[ExecutiveResult]:
    """Process a single organization and return discovered executives."""
    org_name = org.get("name") or "Unknown"
    website = org.get("website")
    company_url = discover_linkedin_company(finder, org_name)
    execs = find_target_executives(finder, company_url, TARGET_TITLES) if company_url else []
    results: List[ExecutiveResult] = []
    for exec_info in execs:
        profile_url = exec_info.get("url")
        contact = extract_contact_info(finder, profile_url) if profile_url else {}
        exec_name = contact.get("name") or exec_info.get("name", "")
        title = contact.get("title") or exec_info.get("title", "")
        emails = predict_email_format(org_name, exec_name, website)
        result = ExecutiveResult(
            org_name=org_name,
            exec_name=exec_name,
            title=title,
            linkedin_url=profile_url,
            emails=emails,
            method="linkedin",
        )
        result.confidence = calculate_confidence_score(result)
        results.append(result)
    return results


def load_checkpoint(path: Path) -> Dict[str, List[dict]]:
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_checkpoint(path: Path, data: Dict[str, List[dict]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def write_results(path: Path, results: List[ExecutiveResult]) -> None:
    file_exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(
                [
                    "org_name",
                    "exec_name",
                    "title",
                    "linkedin_url",
                    "emails",
                    "confidence",
                    "method",
                    "timestamp",
                ]
            )
        for res in results:
            writer.writerow(
                [
                    res.org_name,
                    res.exec_name,
                    res.title,
                    res.linkedin_url or "",
                    ";".join(res.emails),
                    res.confidence,
                    res.method,
                    res.timestamp,
                ]
            )


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LinkedIn contact discovery")
    parser.add_argument("--input", required=True, help="Input CSV of organizations")
    parser.add_argument("--output", required=True, help="Output CSV for executives")
    parser.add_argument("--limit", type=int, default=20, help="Limit number of organizations")
    parser.add_argument("--checkpoint-file", required=True, help="Checkpoint JSON file")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = Path(args.input)
    output_path = Path(args.output)
    checkpoint_path = Path(args.checkpoint_file)
    checkpoint = load_checkpoint(checkpoint_path)

    finder = LinkedInFinder(headless=True, session_rotation=10)
    rotator = SessionRotator(rotate_every=10)

    with input_path.open("r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        count = 0
        for row in reader:
            org_name = row.get("name") or ""
            if org_name in checkpoint:
                logger.info("Skipping %s (already processed)", org_name)
                continue
            results = process_organization(finder, row)
            write_results(output_path, results)
            checkpoint[org_name] = [res.__dict__ for res in results]
            save_checkpoint(checkpoint_path, checkpoint)
            count += 1
            if rotator.increment():
                finder._rotate_session()
            if count >= args.limit:
                break
    finder.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
