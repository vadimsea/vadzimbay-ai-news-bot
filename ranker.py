from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from blocked_sources import BlockedSources, is_news_from_blocked_source
from filters import (
    has_news_event_signal,
    has_required_fields,
    is_low_news_value_material,
    is_political_news,
    is_recent_news,
    is_relevant_tech_news,
)
from storage import PublishedStorage

logger = logging.getLogger(__name__)


MAJOR_TECH_TERMS = {
    "openai", "chatgpt", "google", "deepmind", "anthropic", "claude", "xai", "grok",
    "meta ai", "mistral", "nvidia", "microsoft", "apple", "tesla", "figure ai",
    "unitree", "boston dynamics", "hugging face", "mit", "stanford",
}

IMPORTANT_EVENT_TERMS = {
    "launch", "released", "announced", "unveils", "raises", "funding", "breakthrough",
    "researchers", "model", "robot", "benchmark", "открыл", "представил", "запустил",
    "выпустил", "инвестиции", "раунд", "прорыв", "исследователи", "модель", "робот",
}

BROAD_INTEREST_TERMS = {
    "robot", "robotics", "humanoid", "home robot", "warehouse robot", "factory robot",
    "new model", "ai model", "video generation", "image generation", "voice", "music",
    "medical", "healthcare", "education", "teacher", "design", "business", "gadget",
    "device", "wearable", "breakthrough", "researchers", "startup", "funding",
    "consumer", "product", "app", "assistant", "agent", "automation",
    "web design", "ui design", "ux design", "design trends", "figma", "no-code",
    "marketing ai", "ai marketing", "martech", "adtech", "advertising", "seo",
    "робот", "робототехника", "гуманоид", "бытовой робот", "модель ии", "нейросеть",
    "генерация видео", "генерация изображений", "голос", "музыка", "медицина",
    "образование", "дизайн", "бизнес", "гаджет", "устройство", "стартап",
    "инвестиции", "продукт", "приложение", "ассистент", "автоматизация", "прорыв",
    "веб-дизайн", "веб дизайн", "дизайн сайтов", "ux", "ui", "тренды дизайна",
    "figma", "маркетинг", "ии в маркетинге", "martech", "реклама", "seo",
}

NICHE_DEVELOPER_TERMS = {
    "sdk", "cli", "api", "typescript", "python package", "library", "framework",
    "benchmark", "github", "npm", "vscode", "jetbrains", "kubernetes", "database",
    "open-source agent runtime", "connector", "plugin", "runtime",
    "сдк", "библиотека", "фреймворк", "бенчмарк", "расширение ide", "плагин",
    "коннектор", "рантайм",
}

BORING_TITLE_PATTERNS = {
    "releases sdk", "open-source sdk", "cli and kanban", "benchmark", "technical report",
    "выпустила sdk", "выпустил sdk", "открытый sdk", "бенчмарк",
}


def _published_dt(news: dict[str, Any]) -> datetime:
    try:
        dt = datetime.fromisoformat(str(news.get("published_at", "")).replace("Z", "+00:00"))
    except ValueError:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def score_news(news: dict[str, Any]) -> tuple[float, list[str]]:
    text = f"{news.get('title', '')} {news.get('summary', '')}".lower()
    score = float(news.get("trust_score") or 0.5) * 10
    reasons: list[str] = [f"trust={news.get('trust_score', 0.5)}"]

    age_hours = max((datetime.now(timezone.utc) - _published_dt(news)).total_seconds() / 3600, 0)
    freshness = max(0, 48 - age_hours) / 48
    score += freshness * 20
    reasons.append(f"freshness={freshness:.2f}")

    if any(term in text for term in MAJOR_TECH_TERMS):
        score += 12
        reasons.append("major_brand")

    if any(term in text for term in IMPORTANT_EVENT_TERMS):
        score += 10
        reasons.append("important_event")

    if news.get("image_url"):
        score += 5
        reasons.append("has_image")

    if news.get("category") in {"ai", "robotics"}:
        score += 6
        reasons.append(f"category={news.get('category')}")

    broad_matches = sum(1 for term in BROAD_INTEREST_TERMS if term in text)
    if broad_matches:
        boost = min(14, broad_matches * 3)
        score += boost
        reasons.append(f"broad_interest=+{boost}")

    niche_matches = sum(1 for term in NICHE_DEVELOPER_TERMS if term in text)
    if niche_matches:
        penalty = min(18, niche_matches * 4)
        score -= penalty
        reasons.append(f"niche_developer=-{penalty}")

    title = (news.get("title") or "").lower()
    if any(pattern in title for pattern in BORING_TITLE_PATTERNS):
        score -= 12
        reasons.append("boring_title=-12")

    return score, reasons


def choose_best_news(
    news_items: list[dict[str, Any]],
    storage: PublishedStorage,
    blocked_sources: BlockedSources | None = None,
    max_age_hours: int = 48,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    stats: dict[str, Any] = {
        "total": len(news_items),
        "missing_required_fields": 0,
        "old": 0,
        "duplicates": 0,
        "blocked_sources": 0,
        "irrelevant": 0,
        "low_news_value": 0,
        "political": 0,
        "candidates": 0,
        "selected_reason": "",
    }
    candidates: list[tuple[float, dict[str, Any], list[str]]] = []

    seen_urls: set[str] = set()
    for news in news_items:
        url = str(news.get("url", "")).strip().rstrip("/")
        if not has_required_fields(news):
            stats["missing_required_fields"] += 1
            continue
        if url in seen_urls or storage.is_published(url):
            stats["duplicates"] += 1
            continue
        seen_urls.add(url)
        if blocked_sources and is_news_from_blocked_source(news, blocked_sources):
            stats["blocked_sources"] += 1
            continue
        if not is_recent_news(news, max_age_hours=max_age_hours):
            stats["old"] += 1
            continue
        if is_political_news(news):
            stats["political"] += 1
            continue
        if not is_relevant_tech_news(news):
            stats["irrelevant"] += 1
            continue
        if is_low_news_value_material(news) or not has_news_event_signal(news):
            stats["low_news_value"] += 1
            continue

        score, reasons = score_news(news)
        candidates.append((score, news, reasons))

    stats["candidates"] = len(candidates)
    if not candidates:
        return None, stats

    candidates.sort(key=lambda item: item[0], reverse=True)
    score, selected, reasons = candidates[0]
    stats["selected_reason"] = f"score={score:.1f}; " + ", ".join(reasons)
    logger.info("Selected news: %s (%s)", selected.get("title"), stats["selected_reason"])
    return selected, stats
