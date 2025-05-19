"""Identify and categorize executive contacts from various sources."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Dataclasses
# ----------------------------------------------------------------------

@dataclass
class Contact:
    """Raw contact information from a single source."""

    name: str
    title: str
    source: str
    email: Optional[str] = None
    phone: Optional[str] = None
    updated_at: Optional[datetime] = None


@dataclass
class MatchedContact:
    """Contact matched to a target role with a confidence score."""

    name: str
    title: str
    role: str
    source: str
    score: float
    _raw_score: float = 0.0
    email: Optional[str] = None
    phone: Optional[str] = None
    updated_at: Optional[datetime] = None


# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------

def normalize_title(title: str) -> str:
    """Normalize a title string for matching."""

    title = title.lower()
    title = re.sub(r"[^a-z0-9]+", " ", title)
    title = " ".join(title.split())
    replacements = {
        "cfo": "chief financial officer",
        "gc": "general counsel",
    }
    for abbr, full in replacements.items():
        if title == abbr or title.startswith(f"{abbr} "):
            title = title.replace(abbr, full, 1)
    logger.debug("Normalized title '%s' -> '%s'", title, title)
    return title


def fuzzy_ratio(a: str, b: str) -> float:
    """Return a simple similarity ratio between two strings."""

    return SequenceMatcher(None, a, b).ratio()


# ----------------------------------------------------------------------
# Main identifier
# ----------------------------------------------------------------------

class ContactIdentifier:
    """Identify executive roles from contact records."""

    ROLE_PATTERNS: Dict[str, List[str]] = {
        "General Counsel": ["general counsel", "chief legal officer", "legal counsel"],
        "Deputy General Counsel": ["deputy general counsel", "associate counsel", "assistant general counsel"],
        "CFO": ["chief financial officer", "finance director", "treasurer"],
        "Revenue Officer": ["revenue director", "collections manager"],
    }

    SOURCE_WEIGHTS: Dict[str, float] = {
        "website": 1.0,
        "filing": 0.9,
        "linkedin": 0.8,
        "other": 0.5,
    }

    def __init__(self) -> None:
        self.patterns = {
            role: [normalize_title(p) for p in patterns]
            for role, patterns in self.ROLE_PATTERNS.items()
        }

    # --------------------------------------------------------------
    def _title_score(self, title: str, role: str) -> float:
        normalized = normalize_title(title)
        patterns = self.patterns[role]
        if normalized in patterns:
            return 1.0
        for p in patterns:
            if p in normalized or normalized in p:
                return 0.8
            if fuzzy_ratio(normalized, p) > 0.85:
                return 0.6
        return 0.0

    # --------------------------------------------------------------
    def _completeness_score(self, contact: Contact) -> float:
        score = 0.0
        if contact.name:
            score += 0.2
        if contact.title:
            score += 0.2
        if contact.email or contact.phone:
            score += 0.2
        return score

    # --------------------------------------------------------------
    def _recency_score(self, contact: Contact) -> float:
        if not contact.updated_at:
            return 0.0
        age_days = (datetime.utcnow() - contact.updated_at).days
        if age_days < 365:
            return 0.2
        if age_days < 730:
            return 0.1
        return 0.0

    # --------------------------------------------------------------
    def _source_score(self, contact: Contact) -> float:
        return self.SOURCE_WEIGHTS.get(contact.source, self.SOURCE_WEIGHTS["other"])

    # --------------------------------------------------------------
    def _total_score(self, contact: Contact, role: str) -> float:
        score = 0.0
        score += self._title_score(contact.title, role)
        score += self._source_score(contact)
        score += self._completeness_score(contact)
        score += self._recency_score(contact)
        return score

    # --------------------------------------------------------------
    def categorize_contacts(self, contacts: Iterable[Dict[str, object]]) -> List[MatchedContact]:
        """Match contacts to target roles and return scored results."""

        candidates: Dict[str, List[MatchedContact]] = {role: [] for role in self.patterns}
        for data in contacts:
            contact = Contact(
                name=str(data.get("name", "")),
                title=str(data.get("title", "")),
                source=str(data.get("source", "other")),
                email=data.get("email"),
                phone=data.get("phone"),
                updated_at=data.get("updated_at"),
            )
            for role in self.patterns:
                title_score = self._title_score(contact.title, role)
                if title_score == 0.0:
                    continue
                raw_score = self._total_score(contact, role)
                matched = MatchedContact(
                    name=contact.name,
                    title=contact.title,
                    role=role,
                    source=contact.source,
                    score=min(raw_score / 2.0, 1.0),
                    _raw_score=raw_score,
                    email=contact.email,
                    phone=contact.phone,
                    updated_at=contact.updated_at,
                )
                candidates[role].append(matched)

        results: List[MatchedContact] = []
        for role, matches in candidates.items():
            if not matches:
                continue
            matches.sort(key=lambda m: (m._raw_score, m.score), reverse=True)
            results.append(matches[0])
        return results
