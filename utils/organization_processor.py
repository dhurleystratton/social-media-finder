"""CSV processing utilities for Taft-Hartley Union Trust organizations."""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


@dataclass
class Organization:
    """Data record for a single organization."""

    ein: int
    organization_name: str
    dba_name: str
    entity_type: str
    total_participants: str
    plan_count: int
    mail_us_address1: str
    mail_us_address2: str
    mail_us_city: str
    mail_us_state: str
    mail_us_zip: str
    phone_num: int
    processed: bool = field(default=False)


def normalize_name(name: str) -> str:
    """Normalize organization names for searching."""
    cleaned = re.sub(r"[^a-z0-9]+", " ", name.lower())
    normalized = " ".join(cleaned.split())
    logger.debug("Normalized '%s' -> '%s'", name, normalized)
    return normalized


class OrganizationProcessor:
    """Load and batch process organizations from a CSV file."""

    def __init__(self, csv_path: str | Path) -> None:
        self.csv_path = Path(csv_path)
        self.organizations: Dict[int, Organization] = {}
        self._queue: List[int] = []
        self._processed: set[int] = set()
        self._index = 0
        self._load()

    def _load(self) -> None:
        logger.info("Loading organizations from %s", self.csv_path)
        with self.csv_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    ein = int(row.get("ein", 0))
                except ValueError:
                    logger.warning("Invalid EIN %s", row.get("ein"))
                    continue
                org = Organization(
                    ein=ein,
                    organization_name=row.get("organization_name", ""),
                    dba_name=row.get("dba_name", ""),
                    entity_type=row.get("entity_type", ""),
                    total_participants=row.get("total_participants", ""),
                    plan_count=int(row.get("plan_count", 0) or 0),
                    mail_us_address1=row.get("mail_us_address1", ""),
                    mail_us_address2=row.get("mail_us_address2", ""),
                    mail_us_city=row.get("mail_us_city", ""),
                    mail_us_state=row.get("mail_us_state", ""),
                    mail_us_zip=row.get("mail_us_zip", ""),
                    phone_num=int(row.get("phone_num", 0) or 0),
                )
                self.organizations[ein] = org
                self._queue.append(ein)
        logger.info("Loaded %d organizations", len(self.organizations))

    def get_next_batch(self, *, size: int = 10) -> List[Organization]:
        """Return the next batch of unprocessed organizations."""
        batch: List[Organization] = []
        while len(batch) < size and self._index < len(self._queue):
            ein = self._queue[self._index]
            self._index += 1
            if ein in self._processed:
                continue
            batch.append(self.organizations[ein])
        logger.debug("Returning batch of %d organizations", len(batch))
        return batch

    def mark_processed(self, ein: int) -> None:
        """Mark an organization as processed."""
        if ein in self.organizations:
            self._processed.add(ein)
            self.organizations[ein].processed = True
            logger.debug("Marked EIN %d as processed", ein)

