from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import logging
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import feedparser
import requests

from sources import NewsSource

logger = logging.getLogger(__name__)
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; VadzimbayNewsBot/1.0; +https://t.me/vadzimby_live)"
}


def _clean_html(value: str | None) -> str:
    if not value:
        return ""
    return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)


def _parse_datetime(entry: Any) -> str:
    for key in ("published", "updated", "created"):
        value = entry.get(key)
        if not value:
            continue
        try:
            dt = parsedate_to_datetime(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError, IndexError):
            continue

    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            return datetime(*value[:6], tzinfo=timezone.utc).isoformat()

    return datetime.now(timezone.utc).isoformat()


def _extract_image_url(entry: Any) -> str:
    media_content = entry.get("media_content") or []
    for media in media_content:
        url = media.get("url")
        if url:
            return url

    media_thumbnail = entry.get("media_thumbnail") or []
    for media in media_thumbnail:
        url = media.get("url")
        if url:
            return url

    enclosure = entry.get("enclosures") or []
    for item in enclosure:
        url = item.get("href") or item.get("url")
        mime_type = item.get("type", "")
        if url and mime_type.startswith("image/"):
            return url

    html = entry.get("summary") or entry.get("content", [{}])[0].get("value", "")
    soup = BeautifulSoup(html or "", "html.parser")
    image = soup.find("img")
    if image and image.get("src"):
        return image["src"]

    return ""


def extract_article_image_url(article_url: str) -> str:
    if not article_url:
        return ""

    try:
        response = requests.get(article_url, headers=REQUEST_HEADERS, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        logger.debug("Could not fetch article page for image: %s", article_url)
        return ""

    soup = BeautifulSoup(response.text, "html.parser")
    for selector in (
        ('meta[property="og:image"]', "content"),
        ('meta[name="twitter:image"]', "content"),
        ('meta[property="twitter:image"]', "content"),
    ):
        tag = soup.select_one(selector[0])
        value = tag.get(selector[1]) if tag else ""
        if value:
            return urljoin(article_url, value.strip())

    for image in soup.find_all("img"):
        src = image.get("src") or image.get("data-src") or image.get("data-original")
        if not src:
            continue
        absolute = urljoin(article_url, src.strip())
        if _looks_like_content_image(absolute):
            return absolute

    return ""


def _looks_like_content_image(url: str) -> bool:
    lowered = url.lower()
    bad_parts = ("logo", "avatar", "icon", "sprite", "tracking", "pixel", "banner")
    good_ext = (".jpg", ".jpeg", ".png", ".webp")
    return not any(part in lowered for part in bad_parts) and any(ext in lowered for ext in good_ext)


def _normalize_entry(entry: Any, source: NewsSource) -> dict[str, Any] | None:
    url = (entry.get("link") or entry.get("id") or "").strip()
    title = _clean_html(entry.get("title"))
    summary = _clean_html(entry.get("summary") or entry.get("description"))

    if not url:
        return None

    return {
        "title": title,
        "summary": summary,
        "url": url,
        "image_url": _extract_image_url(entry),
        "published_at": _parse_datetime(entry),
        "language": source.language,
        "source_name": source.name,
        "category": source.category,
        "trust_score": source.trust_score,
    }


def fetch_news_from_source(source: NewsSource) -> list[dict[str, Any]]:
    try:
        parsed = feedparser.parse(source.url)
    except Exception:
        logger.exception("Failed to fetch source: %s", source.name)
        return []

    if parsed.bozo:
        logger.warning("RSS parser warning for %s: %s", source.name, parsed.bozo_exception)

    news: list[dict[str, Any]] = []
    for entry in parsed.entries:
        normalized = _normalize_entry(entry, source)
        if normalized:
            news.append(normalized)

    logger.info("Fetched %s items from %s", len(news), source.name)
    return news


def fetch_all_news(sources: list[NewsSource]) -> list[dict[str, Any]]:
    all_news: list[dict[str, Any]] = []
    for source in sources:
        all_news.extend(fetch_news_from_source(source))
    return all_news
