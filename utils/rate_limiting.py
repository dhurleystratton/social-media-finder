"""Utility helpers for rate limiting."""

from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar


logger = logging.getLogger(__name__)

_T = TypeVar("_T")


def exponential_backoff(func: Callable[..., _T], *, retries: int = 5, base_delay: float = 1.0) -> Callable[..., _T | None]:
    """Wrap a function with exponential backoff retries."""

    def wrapper(*args: object, **kwargs: object) -> _T | None:
        delay = base_delay
        for attempt in range(retries):
            try:
                return func(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Attempt %d failed: %s", attempt + 1, exc)
                time.sleep(delay)
                delay *= 2
        logger.error("All retries failed for %s", func.__name__)
        return None

    return wrapper
