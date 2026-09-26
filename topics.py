from __future__ import annotations

import math
from typing import Any

from filters import has_any_term

AI = "ai"
DEV = "dev"
DESIGN = "design"
MARKETING = "marketing"

# Share of offered news per topic. Soft: quality still decides, see ranker.TOPIC_OVERSHARE_PENALTY.
TOPIC_SHARES: dict[str, float] = {AI: 0.40, DEV: 0.25, MARKETING: 0.20, DESIGN: 0.15}

CATEGORY_TOPICS: dict[str, str] = {
    "ai": AI,
    "robotics": AI,
    "frontend": DEV,
    "backend": DEV,
    "python": DEV,
    "dev": DEV,
    "web_design": DESIGN,
    "design": DESIGN,
    "marketing": MARKETING,
    "marketing_ai": MARKETING,
}

AI_TERMS = {
    "ai", "artificial intelligence", "generative ai", "genai", "llm", "large language model",
    "chatgpt", "openai", "deepmind", "gemini", "anthropic", "claude", "mistral", "xai", "grok",
    "meta ai", "llama", "neural", "machine learning", "foundation model", "copilot", "agentic",
    "ai agent", "coding agent", "vibe coding", "cursor", "windsurf", "midjourney", "sora",
    "ии", "искусственный интеллект", "нейросеть", "нейросети", "нейромодель", "вайбкодинг",
    "ki", "künstliche intelligenz",
}

DEV_TERMS = {
    "python", "django", "fastapi", "flask", "pypi", "pip", "uv", "pytest",
    "javascript", "typescript", "node.js", "nodejs", "deno", "bun", "react", "next.js", "vue",
    "svelte", "angular", "astro", "vite", "webpack", "css", "html", "webassembly", "wasm",
    "frontend", "front-end", "backend", "back-end", "full-stack", "fullstack", "web development",
    "rust", "golang", "kotlin", "swift", "java", "php", "laravel", "c++", "compiler",
    "postgres", "postgresql", "mysql", "sqlite", "redis", "database", "sql", "kafka",
    "docker", "kubernetes", "linux", "git", "github", "gitlab", "open source", "open-source",
    "api", "sdk", "framework", "devops", "microservices", "programming language",
    "developer", "developers", "programmer", "browser", "chrome", "firefox", "safari",
    "питон", "python", "бэкенд", "фронтенд", "разработчик", "разработчики", "программист",
    "программирование", "веб-разработка", "база данных", "открытый код",
}

DESIGN_TERMS = {
    "design", "designer", "designers", "web design", "ui design", "ux design", "ux", "ui", "figma",
    "typography", "typeface", "font", "logo", "rebrand", "rebranding", "branding", "brand identity",
    "illustration", "animation", "motion design", "3d", "photoshop", "illustrator", "canva",
    "framer", "webflow", "sketch", "adobe", "creative cloud", "design system", "landing page",
    "дизайн", "дизайнер", "веб-дизайн", "интерфейс", "типографика", "шрифт", "логотип",
    "ребрендинг", "брендинг", "иллюстрация", "фигма",
}

MARKETING_TERMS = {
    "marketing", "marketer", "marketers", "advertising", "advertiser", "advertisers", "ad campaign",
    "campaign", "seo", "sem", "ppc", "google ads", "meta ads", "tiktok", "instagram", "youtube",
    "social media", "influencer", "creator", "brand", "branding", "conversion", "analytics",
    "content marketing", "email marketing", "martech", "adtech", "crm", "growth", "audience",
    "search ranking", "search engine", "algorithm update", "core update",
    "маркетинг", "маркетолог", "реклама", "рекламная кампания", "соцсети", "инфлюенсер",
    "конверсия", "аналитика", "продвижение", "контент-маркетинг",
}

# Terms that are only weak topic signals in mixed feeds (Hacker News, Habr best): these
# alone do not make a mixed-feed item on-topic for dev/design/marketing.
STRONG_DEV_TERMS = DEV_TERMS - {"api", "sdk", "git", "java", "swift", "bun", "uv", "pip", "sql", "browser", "framework", "developer", "developers"}
STRONG_DESIGN_TERMS = DESIGN_TERMS - {"design", "3d", "adobe", "brand", "animation", "font", "ui", "ux"}
STRONG_MARKETING_TERMS = MARKETING_TERMS - {"brand", "creator", "growth", "analytics", "audience", "campaign", "youtube", "instagram", "tiktok", "crm"}


def topic_of(news: dict[str, Any]) -> str | None:
    """Channel topic of a news item, or None if it is off-topic.

    Topical sources (frontend, design, marketing feeds...) decide by category. Mixed sources
    ("technology", Hacker News, Habr best) are classified by keywords in title and summary.
    """
    category = str(news.get("category") or "").lower()
    if category in CATEGORY_TOPICS:
        return CATEGORY_TOPICS[category]

    text = f"{news.get('title', '')} {news.get('summary', '')}".lower()
    if has_any_term(text, AI_TERMS):
        return AI
    if has_any_term(text, STRONG_DEV_TERMS):
        return DEV
    if has_any_term(text, STRONG_DESIGN_TERMS):
        return DESIGN
    if has_any_term(text, STRONG_MARKETING_TERMS):
        return MARKETING
    return None


def topic_quotas(total: int) -> dict[str, int]:
    return {topic: max(1, math.ceil(total * share)) for topic, share in TOPIC_SHARES.items()}
