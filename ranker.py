from __future__ import annotations

from datetime import datetime, timezone
import logging
import re
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
    "frontend", "front-end", "web development", "javascript", "typescript", "react",
    "next.js", "vue", "svelte", "css", "accessibility", "performance",
    "marketing ai", "ai marketing", "martech", "adtech", "advertising", "seo",
    "content marketing", "conversion", "analytics", "growth",
    "vibe coding", "vibecoding", "ai coding", "coding agent", "code agent",
    "ai programming", "prompt-to-code", "agentic coding", "cursor", "windsurf",
    "lovable", "bolt.new", "replit agent", "claude code",
    "робот", "робототехника", "гуманоид", "бытовой робот", "модель ии", "нейросеть",
    "генерация видео", "генерация изображений", "голос", "музыка", "медицина",
    "образование", "дизайн", "бизнес", "гаджет", "устройство", "стартап",
    "инвестиции", "продукт", "приложение", "ассистент", "автоматизация", "прорыв",
    "веб-дизайн", "веб дизайн", "дизайн сайтов", "ux", "ui", "тренды дизайна",
    "figma", "фронтенд", "веб-разработка", "react", "next.js", "css",
    "маркетинг", "ии в маркетинге", "martech", "реклама", "seo",
    "контент-маркетинг", "конверсия", "аналитика",
    "вайбкодинг", "вайб-кодинг", "ии для кода", "ии-программирование",
    "кодинг-агент", "генерация кода", "программирование с ии",
}

AUTHORITATIVE_US_EU_SOURCES = {
    "techcrunch ai", "the verge ai", "mit technology review", "ars technica",
    "venturebeat ai", "wired", "the decoder", "ieee spectrum robotics",
    "sciencedaily robotics", "google deepmind blog", "openai blog",
    "anthropic news", "nvidia blog", "smashing magazine", "css-tricks",
    "a list apart", "search engine land", "marketing ai institute",
    "heise online", "golem.de", "t3n", "omr", "computerbase",
}

AI_CORE_TERMS = {
    "ai", "artificial intelligence", "llm", "neural", "model", "agent",
    "openai", "deepmind", "anthropic", "mistral", "xai", "nvidia",
    "ии", "искусственный интеллект", "нейросеть", "модель", "агент",
}

WEB_MARKETING_TERMS = {
    "web design", "frontend", "front-end", "ui", "ux", "figma", "react",
    "next.js", "css", "marketing", "seo", "martech", "advertising",
    "веб-дизайн", "фронтенд", "маркетинг", "реклама", "конверсия",
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
    "developer preview", "patch notes", "release notes", "minor update", "data-backed truths",
    "truths of user experience", "roi", "case study", "what i learned", "how i", "how to",
    "guide", "tutorial", "weekly", "roundup", "video friday", "dashboard rolls out",
    "offline conversion imports", "citations dashboard", "personal finance", "bank accounts",
    "выпустила sdk", "выпустил sdk", "открытый sdk", "бенчмарк", "заметки к релизу",
    "минорное обновление",
}

LOW_BROAD_VALUE_TERMS = {
    "internal tool", "enterprise-only", "api endpoint", "migration guide", "deprecated",
    "breaking changes", "syntax", "configuration", "command line flag", "citations dashboard",
    "offline conversion", "dashboard shows", "data-backed facts", "measurable business cost",
    "personal finance", "bank-to-app", "bank accounts", "tips", "best practices",
    "внутренний инструмент", "руководство по миграции", "устаревший", "конфигурация",
}

WOW_SIGNAL_TERMS = {
    "launches", "launched", "releases", "released", "unveils", "introduces", "announces",
    "new model", "frontier model", "reasoning model", "multimodal model", "video model",
    "image model", "voice model", "coding agent", "ai agent", "agentic", "vibe coding",
    "claude code", "cursor", "windsurf", "lovable", "bolt.new", "replit agent",
    "figma ai", "design tool", "marketing ai", "automation", "breakthrough", "raises",
    "funding", "open source", "open-source", "beats", "outperforms", "faster than",
}

EDITORIAL_REJECT_TERMS = {
    "data-backed truths", "truths of user experience", "roi", "case study", "how to",
    "guide", "tutorial", "tips", "best practices", "roundup", "weekly", "video friday",
    "dashboard rolls out", "citations dashboard", "offline conversion imports",
    "personal finance", "bank accounts", "bank-to-app", "what i learned",
}


def _published_dt(news: dict[str, Any]) -> datetime:
    try:
        dt = datetime.fromisoformat(str(news.get("published_at", "")).replace("Z", "+00:00"))
    except ValueError:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def score_news(news: dict[str, Any], topic_count: int = 1) -> tuple[float, list[str]]:
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

    language = str(news.get("language") or "").lower()
    if language in {"en", "de", "zh", "he"}:
        score += 14
        reasons.append(f"foreign_language=+14:{language}")
    elif language == "ru":
        score += 1
        reasons.append("russian_language=+1")

    broad_matches = sum(1 for term in BROAD_INTEREST_TERMS if term in text)
    if broad_matches:
        boost = min(14, broad_matches * 3)
        score += boost
        reasons.append(f"broad_interest=+{boost}")

    source_name = str(news.get("source_name") or "").lower()
    if source_name in AUTHORITATIVE_US_EU_SOURCES:
        score += 12
        reasons.append("authoritative_us_eu=+12")

    category = str(news.get("category") or "").lower()
    has_ai_signal = category in {"ai", "robotics", "marketing_ai"} or any(term in text for term in AI_CORE_TERMS)
    has_web_marketing_signal = category in {"web_design", "frontend", "marketing", "marketing_ai"} or any(
        term in text for term in WEB_MARKETING_TERMS
    )
    if has_ai_signal:
        score += 8
        reasons.append("ai_core=+8")
    if has_web_marketing_signal:
        score += 7
        reasons.append("web_marketing_frontend=+7")

    niche_matches = sum(1 for term in NICHE_DEVELOPER_TERMS if term in text)
    if niche_matches:
        penalty = min(18, niche_matches * 4)
        score -= penalty
        reasons.append(f"niche_developer=-{penalty}")

    title = (news.get("title") or "").lower()
    if any(pattern in title for pattern in BORING_TITLE_PATTERNS):
        score -= 12
        reasons.append("boring_title=-12")

    low_value_matches = sum(1 for term in LOW_BROAD_VALUE_TERMS if term in text)
    if low_value_matches:
        penalty = min(12, low_value_matches * 4)
        score -= penalty
        reasons.append(f"low_broad_value=-{penalty}")

    if topic_count > 1:
        boost = min(10, (topic_count - 1) * 4)
        score += boost
        reasons.append(f"multi_source=+{boost}:{topic_count}")

    return score, reasons


def choose_best_news(
    news_items: list[dict[str, Any]],
    storage: PublishedStorage,
    blocked_sources: BlockedSources | None = None,
    max_age_hours: int = 48,
    source_cooldown_recent_posts: int = 2,
    llm_selector=None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    selected_items, stats = choose_top_news(
        news_items=news_items,
        storage=storage,
        blocked_sources=blocked_sources,
        max_age_hours=max_age_hours,
        source_cooldown_recent_posts=source_cooldown_recent_posts,
        selection_count=1,
        llm_selector=llm_selector,
    )
    return (selected_items[0] if selected_items else None), stats


def choose_top_news(
    news_items: list[dict[str, Any]],
    storage: PublishedStorage,
    blocked_sources: BlockedSources | None = None,
    max_age_hours: int = 48,
    source_cooldown_recent_posts: int = 2,
    selection_count: int = 3,
    llm_selector=None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    stats: dict[str, Any] = {
        "total": len(news_items),
        "missing_required_fields": 0,
        "old": 0,
        "duplicates": 0,
        "blocked_sources": 0,
        "source_cooldown": 0,
        "irrelevant": 0,
        "off_topic_priority": 0,
        "low_news_value": 0,
        "political": 0,
        "candidates": 0,
        "selected_reason": "",
        "selected_reasons": [],
    }
    candidates: list[tuple[float, dict[str, Any], list[str]]] = []
    topic_counts = _build_topic_counts(news_items)
    recent_sources = _recent_published_sources(storage, source_cooldown_recent_posts)

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
        if _source_name(news) in recent_sources:
            stats["source_cooldown"] += 1
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
        if not _is_priority_channel_news(news):
            stats["off_topic_priority"] += 1
            continue
        if not _has_editorial_value(news):
            stats["low_news_value"] += 1
            continue
        if is_low_news_value_material(news) or not has_news_event_signal(news):
            stats["low_news_value"] += 1
            continue

        topic_key = _topic_key(news)
        score, reasons = score_news(news, topic_count=topic_counts.get(topic_key, 1))
        candidates.append((score, news, reasons))

    stats["candidates"] = len(candidates)
    if not candidates:
        return [], stats

    candidates.sort(key=lambda item: item[0], reverse=True)
    selected_items: list[dict[str, Any]] = []
    selected_reasons: list[str] = []
    source_counts: dict[str, int] = {}

    if llm_selector:
        foreign_candidates = [
            item[1]
            for item in candidates
            if str(item[1].get("language") or "").lower() in {"en", "de", "zh", "he"}
        ][:20]
        llm_pool = foreign_candidates if len(foreign_candidates) >= 3 else [item[1] for item in candidates[:20]]
        llm_news, llm_reason = llm_selector(llm_pool)
        if llm_news:
            selected_items.append(llm_news)
            source_counts[_source_name(llm_news)] = 1
            selected_reasons.append(f"llm_selected; {llm_reason}")
            logger.info("LLM selected news: %s (%s)", llm_news.get("title"), selected_reasons[-1])

    foreign_available = sum(
        1
        for _, news, _ in candidates
        if _is_foreign(news)
        and not any(_normalize_url(item.get("url", "")) == _normalize_url(news.get("url", "")) for item in selected_items)
    )
    for score, news, reasons in candidates:
        if len(selected_items) >= selection_count:
            break
        if any(_normalize_url(item.get("url", "")) == _normalize_url(news.get("url", "")) for item in selected_items):
            continue
        if not _is_foreign(news) and foreign_available >= selection_count - len(selected_items):
            continue
        source_name = _source_name(news)
        selected_items.append(news)
        source_counts[source_name] = source_counts.get(source_name, 0) + 1
        selected_reasons.append(f"score={score:.1f}; " + ", ".join(reasons))

    if len(selected_items) < selection_count:
        for score, news, reasons in candidates:
            if len(selected_items) >= selection_count:
                break
            if any(_normalize_url(item.get("url", "")) == _normalize_url(news.get("url", "")) for item in selected_items):
                continue
            if not _is_foreign(news):
                continue
            selected_items.append(news)
            selected_reasons.append(f"score={score:.1f}; " + ", ".join(reasons))

    if len(selected_items) < selection_count:
        for score, news, reasons in candidates:
            if len(selected_items) >= selection_count:
                break
            if any(_normalize_url(item.get("url", "")) == _normalize_url(news.get("url", "")) for item in selected_items):
                continue
            selected_items.append(news)
            selected_reasons.append(f"score={score:.1f}; " + ", ".join(reasons))

    stats["selected_reasons"] = selected_reasons
    stats["selected_reason"] = selected_reasons[0] if selected_reasons else ""
    for news, reason in zip(selected_items, selected_reasons):
        logger.info("Selected news option: %s (%s)", news.get("title"), reason)
    return selected_items, stats


def _build_topic_counts(news_items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    seen_source_by_topic: dict[str, set[str]] = {}
    for news in news_items:
        key = _topic_key(news)
        if not key:
            continue
        source = str(news.get("source_name") or news.get("url") or "")
        seen_source_by_topic.setdefault(key, set()).add(source)
    for key, sources in seen_source_by_topic.items():
        counts[key] = len(sources)
    return counts


def _recent_published_sources(storage: PublishedStorage, limit: int) -> set[str]:
    if limit <= 0:
        return set()
    sources: set[str] = set()
    for item in storage.load_published()[-limit:]:
        if item.get("status", "published") != "published":
            continue
        metadata = item.get("metadata") or {}
        source_name = str(metadata.get("source_name") or "").strip().lower()
        if source_name:
            sources.add(source_name)
    return sources


def _source_name(news: dict[str, Any]) -> str:
    return str(news.get("source_name") or "").strip().lower()


def _is_foreign(news: dict[str, Any]) -> bool:
    return str(news.get("language") or "").lower() in {"en", "de", "zh", "he"}


def _normalize_url(url: Any) -> str:
    return str(url or "").strip().rstrip("/")


def _is_priority_channel_news(news: dict[str, Any]) -> bool:
    category = str(news.get("category") or "").lower()
    title = str(news.get("title") or "").lower()
    text = f"{news.get('title', '')} {news.get('summary', '')} {news.get('source_name', '')}".lower()

    ai_terms = {
        "ai", "artificial intelligence", "generative ai", "genai", "llm", "large language model",
        "chatgpt", "openai", "deepmind", "gemini", "anthropic", "claude", "mistral", "xai",
        "grok", "meta ai", "llama", "neural", "machine learning", "foundation model",
        "image generation", "video generation", "voice model", "multimodal", "agentic",
        "copilot", "nvidia ai",
        "ии", "искусственный интеллект", "нейросеть", "нейросети", "нейромодель",
    }
    vibe_coding_terms = {
        "vibe coding", "vibecoding", "ai coding", "coding agent", "code agent", "claude code",
        "cursor", "windsurf", "lovable", "bolt.new", "replit agent", "prompt-to-code",
        "agentic coding", "ai developer", "ai programming",
        "вайбкодинг", "вайб-кодинг", "ии для кода", "кодинг-агент",
    }
    web_design_terms = {
        "web design", "website design", "webdesign", "ui design", "ux design", "ux/ui",
        "design trends", "figma", "frontend", "front-end", "web development", "react",
        "next.js", "css", "creative tool", "design system", "accessibility",
        "веб-дизайн", "веб дизайн", "дизайн сайтов", "фронтенд", "интерфейс",
    }
    marketing_terms = {
        "ai marketing", "marketing ai", "martech", "adtech", "advertising ai",
        "seo", "content marketing", "conversion", "analytics", "growth marketing",
        "crm", "marketing automation", "campaign",
        "маркетинг", "реклама", "конверсия", "аналитика",
    }

    if category in {"ai", "marketing_ai", "web_design", "frontend"}:
        return True
    if category == "marketing":
        return _has_any(text, marketing_terms | ai_terms)
    if category == "robotics":
        return _has_any(title, ai_terms | vibe_coding_terms)
    return _has_any(text, ai_terms | vibe_coding_terms | web_design_terms | marketing_terms)


def _has_editorial_value(news: dict[str, Any]) -> bool:
    category = str(news.get("category") or "").lower()
    title = str(news.get("title") or "").lower()
    text = f"{news.get('title', '')} {news.get('summary', '')}".lower()

    if any(term in title for term in EDITORIAL_REJECT_TERMS):
        return False

    if category in {"web_design", "frontend", "marketing"} and not _has_any(text, WOW_SIGNAL_TERMS):
        return False

    if category == "technology" and not _has_any(text, WOW_SIGNAL_TERMS):
        return False

    has_major_ai_brand = any(
        brand in text
        for brand in (
            "openai", "chatgpt", "anthropic", "claude", "google deepmind",
            "gemini", "xai", "grok", "mistral", "meta ai", "llama", "cursor",
            "windsurf", "figma", "nvidia",
        )
    )
    has_wow_signal = _has_any(text, WOW_SIGNAL_TERMS)
    has_work_value = _has_any(
        text,
        {
            "coding agent", "code assistant", "marketing automation", "design tool",
            "figma", "frontend", "conversion", "content marketing", "workflow",
            "agent", "automation", "model", "launches", "released", "unveils",
        },
    )
    return has_major_ai_brand or has_wow_signal or has_work_value


def _has_any(text: str, terms: set[str]) -> bool:
    for term in terms:
        if term in {"ai", "ии", "ui", "ux", "seo", "css"}:
            if re.search(r"(?<![\wа-яё])" + re.escape(term) + r"(?![\wа-яё])", text):
                return True
            continue
        if term in text:
            return True
    return False


def _topic_key(news: dict[str, Any]) -> str:
    title = str(news.get("title") or "").lower()
    title = re.sub(r"https?://\S+", " ", title)
    title = re.sub(r"[^a-zа-яё0-9\s]+", " ", title)
    stop_words = {
        "the", "and", "for", "with", "from", "that", "this", "into", "over", "new",
        "как", "что", "это", "для", "или", "при", "над", "под", "новый", "новая",
        "der", "die", "das", "und", "mit", "ein", "eine", "neue", "neuer",
    }
    words = [word for word in title.split() if len(word) > 2 and word not in stop_words]
    return " ".join(words[:8])
