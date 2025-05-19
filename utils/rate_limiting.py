"""Utility helpers for rate limiting."""

from __future__ import annotations

import logging
import random
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


def linkedin_delay(min_delay: float = 30.0, max_delay: float = 90.0) -> None:
    """Sleep with jitter for LinkedIn requests."""

    delay = random.uniform(min_delay, max_delay)
    jitter = random.uniform(0, 5)
    total = delay + jitter
    logger.debug("Sleeping %.2f seconds for LinkedIn pacing", total)
    time.sleep(total)


class SessionRotator:
    """Utility for rotating sessions after N operations."""

    def __init__(self, rotate_every: int = 5) -> None:
        self.rotate_every = rotate_every
        self.counter = 0

    def increment(self) -> bool:
        """Increase counter and return True if rotation is due."""

        self.counter += 1
        if self.counter >= self.rotate_every:
            self.counter = 0
            return True
        return False
