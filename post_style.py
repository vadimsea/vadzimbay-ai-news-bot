from __future__ import annotations

import random
import re
from typing import Any


DEFAULT_EMOJIS = ("🚀", "⚡", "✨")

EMOJI_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("🤖", ("robot", "robotics", "humanoid", "робот", "робототехника", "гуманоид")),
    ("🧠", ("ai", "artificial intelligence", "neural", "llm", "ии", "нейросеть", "модель")),
    ("📱", ("gadget", "device", "smartphone", "wearable", "гаджет", "устройство", "смартфон")),
    ("🎨", ("web design", "ui", "ux", "figma", "design", "веб-дизайн", "дизайн", "интерфейс")),
    ("🧩", ("frontend", "front-end", "web development", "react", "next.js", "css", "фронтенд", "веб-разработка")),
    ("📈", ("marketing", "martech", "advertising", "seo", "crm", "маркетинг", "реклама")),
    ("⌨️", ("vibe coding", "vibecoding", "вайбкодинг", "вайб-кодинг", "ai coding", "coding agent", "cursor", "windsurf", "claude code")),
    ("🔬", ("research", "study", "scientists", "исследование", "исследователи", "ученые")),
    ("🔐", ("security", "cyber", "vulnerability", "кибербезопас", "уязвимость")),
    ("💡", ("startup", "funding", "investment", "стартап", "инвестиции")),
]


def pick_title_emoji(news: dict[str, Any]) -> str:
    text = f"{news.get('title', '')} {news.get('summary', '')} {news.get('category', '')}".lower()
    matches = [emoji for emoji, keywords in EMOJI_RULES if any(keyword in text for keyword in keywords)]
    return random.choice(matches or list(DEFAULT_EMOJIS))


def apply_title_emoji(text: str, news: dict[str, Any]) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        clean_title = re.sub(r"^[^\wА-Яа-яЁёA-Za-z0-9#@]+", "", line).strip()
        lines[index] = f"{pick_title_emoji(news)} {clean_title}"
        return "\n".join(lines)
    return text
