"""Twitter/X platform integration."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import tweepy

logger = logging.getLogger(__name__)

class TwitterFinder:
    """Basic Twitter API wrapper for finding profiles."""

    def __init__(self, api_key: str, api_secret: str | None = None, bearer_token: str | None = None) -> None:
        if bearer_token:
            self.client = tweepy.Client(bearer_token)
        else:
            auth = tweepy.OAuth1UserHandler(api_key, api_secret)
            self.client = tweepy.API(auth)

    def find_profile(self, query: str, **kwargs: Any) -> List[Dict[str, Any]]:
        """Search for profiles matching the query."""
        try:
            logger.debug("Searching Twitter for %s", query)
            if hasattr(self.client, "search_users"):
                users = self.client.search_users(q=query)
            else:
                response = self.client.search_users(query)
                users = response.data if response else []
            results = []
            for user in users:
                results.append({"username": getattr(user, "screen_name", None) or user.username, "id": user.id})
            return results
        except tweepy.TweepyException as exc:
            logger.error("Twitter API error: %s", exc)
            return []
