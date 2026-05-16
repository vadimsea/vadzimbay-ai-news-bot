from __future__ import annotations

import re
from typing import Any


MAX_HASHTAGS = 4

TAG_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("#ИИ", ("ai", "artificial intelligence", "искусственный интеллект", "ии", "ki")),
    ("#Нейросети", ("neural", "нейросеть", "нейросети", "llm", "model", "модель")),
    ("#Роботы", ("robot", "robotics", "робот", "робототехника", "roboter")),
    ("#Гаджеты", ("gadget", "device", "wearable", "гаджет", "устройство")),
    ("#Стартапы", ("startup", "funding", "raises", "инвестиции", "стартап")),
    ("#Кибербезопасность", ("security", "cyber", "vulnerability", "уязвимость", "кибербезопас")),
    ("#Автоматизация", ("automation", "agent", "workflow", "автоматизация", "агент")),
    ("#ВебДизайн", ("web design", "website design", "webdesign", "веб-дизайн", "веб дизайн", "дизайн сайтов")),
    ("#UXUI", ("ux", "ui", "ux/ui", "user experience", "interface", "интерфейс")),
    ("#Frontend", ("frontend", "front-end", "web development", "javascript", "typescript", "react", "next.js", "vue", "svelte", "css", "фронтенд", "веб-разработка")),
    ("#Маркетинг", ("marketing", "маркетинг", "martech", "adtech", "advertising", "реклама", "seo", "crm")),
    ("#Вайбкодинг", ("vibe coding", "vibecoding", "вайбкодинг", "вайб-кодинг", "ai coding", "coding agent", "cursor", "windsurf", "claude code", "lovable", "bolt.new")),
    ("#Наука", ("research", "researchers", "study", "исследователи", "исследование")),
    ("#OpenAI", ("openai", "chatgpt")),
    ("#Google", ("google", "deepmind", "gemini")),
    ("#Apple", ("apple", "macos", "iphone", "ipad")),
    ("#NVIDIA", ("nvidia", "gpu")),
    ("#Anthropic", ("anthropic", "claude")),
    ("#Meta", ("meta ai", "llama")),
    ("#Microsoft", ("microsoft", "copilot")),
]

FALLBACK_TAGS = ("#Технологии", "#Будущее")


def build_hashtags(news: dict[str, Any], max_tags: int = MAX_HASHTAGS) -> list[str]:
    text = f"{news.get('title', '')} {news.get('summary', '')} {news.get('source_name', '')}".lower()
    tags: list[str] = []

    for tag, keywords in TAG_RULES:
        if any(_keyword_matches(text, keyword) for keyword in keywords):
            tags.append(tag)
        if len(tags) >= max_tags:
            return tags

    for tag in FALLBACK_TAGS:
        if tag not in tags:
            tags.append(tag)
        if len(tags) >= max_tags:
            break

    return tags


def append_hashtags(text: str, news: dict[str, Any], max_length: int = 1024) -> str:
    tags = build_hashtags(news)
    while tags:
        candidate = f"{text.rstrip()}\n\n{' '.join(tags)}"
        if len(candidate) <= max_length:
            return candidate
        tags.pop()
    return text


def _keyword_matches(text: str, keyword: str) -> bool:
    keyword = keyword.lower()
    if keyword in {"ai", "ии", "ki", "ui", "ux", "seo", "crm", "frontend", "front-end"}:
        return re.search(r"(?<![\wа-яё])" + re.escape(keyword) + r"(?![\wа-яё])", text) is not None
    return keyword in text
