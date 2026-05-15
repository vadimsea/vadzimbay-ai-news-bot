from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sources import NewsSource

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BlockedSources:
    domains: set[str] = field(default_factory=set)
    source_names: set[str] = field(default_factory=set)
    keywords: set[str] = field(default_factory=set)


def load_blocked_sources(path: Path) -> BlockedSources:
    if not path.exists():
        logger.info("Blocked sources file not found, using empty denylist: %s", path)
        return BlockedSources()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Could not read blocked sources file: %s", path)
        return BlockedSources()

    return BlockedSources(
        domains={_normalize_domain(value) for value in _as_list(raw.get("domains")) if value},
        source_names={str(value).strip().lower() for value in _as_list(raw.get("source_names")) if value},
        keywords={str(value).strip().lower() for value in _as_list(raw.get("keywords")) if value},
    )


def is_source_blocked(source: NewsSource, blocked: BlockedSources) -> bool:
    source_domain = _normalize_domain(source.url)
    source_name = source.name.strip().lower()
    text = f"{source.name} {source.url}".lower()
    return (
        _domain_is_blocked(source_domain, blocked.domains)
        or source_name in blocked.source_names
        or any(keyword in text for keyword in blocked.keywords)
    )


def is_news_from_blocked_source(news: dict[str, Any], blocked: BlockedSources) -> bool:
    url_domain = _normalize_domain(str(news.get("url") or ""))
    source_name = str(news.get("source_name") or "").strip().lower()
    text = f"{news.get('source_name', '')} {news.get('url', '')}".lower()
    return (
        _domain_is_blocked(url_domain, blocked.domains)
        or source_name in blocked.source_names
        or any(keyword in text for keyword in blocked.keywords)
    )


def filter_allowed_sources(sources: list[NewsSource], blocked: BlockedSources) -> tuple[list[NewsSource], list[NewsSource]]:
    allowed: list[NewsSource] = []
    rejected: list[NewsSource] = []
    for source in sources:
        if is_source_blocked(source, blocked):
            rejected.append(source)
        else:
            allowed.append(source)
    return allowed, rejected


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _normalize_domain(value: str) -> str:
    raw = str(value).strip().lower()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = parsed.netloc or parsed.path
    return host.removeprefix("www.").strip("/")


def _domain_is_blocked(domain: str, blocked_domains: set[str]) -> bool:
    if not domain:
        return False
    return any(domain == blocked or domain.endswith(f".{blocked}") for blocked in blocked_domains)
