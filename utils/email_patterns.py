from __future__ import annotations

"""Email prediction and verification utilities."""

from dataclasses import dataclass
from typing import Iterable, List, Dict, Optional
import logging
import re
import time
from urllib.parse import urlparse

try:
    import dns.resolver  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    dns = None

import smtplib

logger = logging.getLogger(__name__)


EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


@dataclass
class EmailCandidate:
    """Represents a generated email with confidence."""

    email: str
    confidence: float = 0.0


class EmailPatternGenerator:
    """Generate and verify possible executive email addresses."""

    PATTERN_WEIGHTS: Dict[str, float] = {
        "first.last": 0.4,
        "flast": 0.3,
        "firstname": 0.1,
        "f.last": 0.2,
        "first_last": 0.1,  # industry specific
    }

    def __init__(self, *, rate_limit: float = 1.0) -> None:
        self.rate_limit = rate_limit
        self._last_check = 0.0
        self._verify_cache: Dict[str, bool] = {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _split_name(name: str) -> tuple[str, str]:
        parts = [p for p in name.strip().lower().split() if p]
        first = parts[0] if parts else ""
        last = parts[-1] if len(parts) > 1 else ""
        return first, last

    @staticmethod
    def _extract_domain(url: str) -> str:
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path
        if host.startswith("www."):
            host = host[4:]
        return host.lower()

    def discover_domain(self, contact: Dict[str, str]) -> Optional[str]:
        """Attempt to determine an organization's domain."""

        if contact.get("email"):
            return contact["email"].split("@")[-1].lower()
        if contact.get("website"):
            return self._extract_domain(contact["website"])
        if contact.get("domain"):
            return self._extract_domain(contact["domain"])
        org = contact.get("organization")
        if org:
            base = re.sub(r"[^a-z0-9]+", "", org.lower())
            if base:
                return f"{base}.com"
        return None

    # ------------------------------------------------------------------
    def generate_candidates(self, contact: Dict[str, str]) -> List[EmailCandidate]:
        """Generate possible email addresses for a contact."""

        domain = self.discover_domain(contact)
        if not domain:
            return []
        first, last = self._split_name(contact.get("name", ""))
        if not first:
            return []
        fi = first[0]
        patterns = {
            "first.last": f"{first}.{last}@{domain}" if last else f"{first}@{domain}",
            "flast": f"{fi}{last}@{domain}" if last else f"{fi}@{domain}",
            "firstname": f"{first}@{domain}",
            "f.last": f"{fi}.{last}@{domain}" if last else f"{fi}@{domain}",
            "first_last": f"{first}_{last}@{domain}" if last else f"{first}@{domain}",
        }
        candidates = [
            EmailCandidate(email=email, confidence=self.PATTERN_WEIGHTS.get(key, 0.1))
            for key, email in patterns.items()
        ]
        return candidates

    # ------------------------------------------------------------------
    def _respect_rate_limit(self) -> None:
        elapsed = time.time() - self._last_check
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_check = time.time()

    def _check_mx(self, domain: str) -> bool:
        if not dns:
            return False
        try:
            dns.resolver.resolve(domain, "MX")
            return True
        except Exception:  # noqa: BLE001
            return False

    def _smtp_check(self, email: str) -> bool:
        domain = email.split("@")[-1]
        if not dns:
            return False
        try:
            records = dns.resolver.resolve(domain, "MX")
            host = str(sorted(records, key=lambda r: r.preference)[0].exchange)
        except Exception:  # noqa: BLE001
            return False
        try:
            self._respect_rate_limit()
            with smtplib.SMTP(host, timeout=10) as smtp:
                smtp.helo()
                smtp.mail("<>")
                code, _ = smtp.rcpt(email)
                return code in (250, 251)
        except Exception:  # noqa: BLE001
            return False

    # ------------------------------------------------------------------
    def verify_emails(self, candidates: Iterable[EmailCandidate]) -> List[EmailCandidate]:
        """Verify generated emails and update confidence."""

        verified: List[EmailCandidate] = []
        for cand in candidates:
            email = cand.email
            if email in self._verify_cache:
                ok = self._verify_cache[email]
                if ok:
                    verified.append(cand)
                continue
            if not EMAIL_RE.fullmatch(email):
                self._verify_cache[email] = False
                continue
            domain = email.split("@")[-1]
            mx_ok = self._check_mx(domain)
            smtp_ok = self._smtp_check(email) if mx_ok else False
            score = cand.confidence
            if mx_ok:
                score += 0.2
            if smtp_ok:
                score += 0.3
            if mx_ok and smtp_ok:
                score += 0.1
            if mx_ok:
                cand.confidence = min(score, 1.0)
                verified.append(cand)
                self._verify_cache[email] = True
            else:
                self._verify_cache[email] = False
        return verified

    # ------------------------------------------------------------------
    @staticmethod
    def get_best_match(candidates: Iterable[EmailCandidate]) -> Optional[EmailCandidate]:
        """Return the highest confidence email."""

        sorted_cands = sorted(candidates, key=lambda c: c.confidence, reverse=True)
        return sorted_cands[0] if sorted_cands else None


__all__ = ["EmailPatternGenerator", "EmailCandidate"]
