import re
import socket
from typing import List, Optional

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover - fallback when requests not installed
    requests = None


class DomainGuesser:
    """Guess possible domains for an organization name."""

    COMMON_TLDS: List[str] = [".com", ".org", ".net", ".us"]

    def __init__(self, tlds: Optional[List[str]] = None) -> None:
        self.tlds = tlds or self.COMMON_TLDS

    @staticmethod
    def _normalize(name: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", name.lower())

    def generate_candidates(self, name: str) -> List[str]:
        base = self._normalize(name)
        if not base:
            return []
        candidates: List[str] = []
        for tld in self.tlds:
            candidates.append(f"{base}{tld}")
        return candidates

    def guess(self, name: str) -> Optional[str]:
        for domain in self.generate_candidates(name):
            if self._domain_exists(domain):
                return domain
        return None

    def _domain_exists(self, domain: str) -> bool:
        """Check whether a domain resolves or responds."""
        try:
            socket.gethostbyname(domain)
        except Exception:
            return False
        if requests:
            try:
                resp = requests.head(f"https://{domain}", timeout=5)
                if resp.status_code < 400:
                    return True
            except Exception:
                pass
        return True
