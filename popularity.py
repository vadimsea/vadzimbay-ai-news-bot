from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"


def url_key(url: str) -> str:
    """Host + path without scheme, "www.", query, fragment and trailing slash."""
    parsed = urlparse((url or "").strip())
    host = parsed.netloc.lower().removeprefix("www.")
    return f"{host}{parsed.path.rstrip('/')}".lower()


def fetch_hn_stories(hours: int = 96, min_points: int = 20, timeout: int = 15) -> list[dict[str, Any]]:
    """Recent Hacker News stories with at least `min_points`. Empty list on any failure."""
    since = int(time.time()) - hours * 3600
    params = {
        "tags": "story",
        "numericFilters": f"points>={min_points},created_at_i>{since}",
        "hitsPerPage": 1000,
    }
    try:
        response = requests.get(HN_SEARCH_URL, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json().get("hits", [])
    except (requests.RequestException, ValueError):
        logger.warning("Could not load Hacker News stories, continuing without them", exc_info=True)
        return []


def fetch_hn_popularity(hours: int = 96, min_points: int = 20, timeout: int = 15) -> dict[str, int]:
    """Hacker News points for recent stories, keyed by url_key. Empty dict on any failure."""
    hits = fetch_hn_stories(hours, min_points, timeout)
    table: dict[str, int] = {}
    for hit in hits:
        url = hit.get("url")
        if not url:
            continue
        key = url_key(url)
        table[key] = max(table.get(key, 0), int(hit.get("points") or 0))
    logger.info("Hacker News popularity loaded: %s stories", len(table))
    return table


def popularity_points(news: dict[str, Any], table: dict[str, int]) -> int:
    return table.get(url_key(str(news.get("url") or "")), 0)
