from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
import os


BASE_DIR = Path(__file__).resolve().parent


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_channel_id: str
    openai_api_key: str | None
    groq_api_key: str | None
    llm_provider: str
    post_time: str
    morning_window: str
    evening_window: str
    timezone: str
    max_news_age_hours: int
    source_cooldown_recent_posts: int
    dry_run: bool
    moderation_enabled: bool
    moderation_chat_id: str
    moderation_timeout_minutes: int
    moderation_choices: int
    published_file: Path
    blocked_sources_file: Path
    request_timeout_seconds: int
    openai_model: str
    groq_model: str


def load_settings() -> Settings:
    load_dotenv(BASE_DIR / ".env")

    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_channel_id=os.getenv("TELEGRAM_CHANNEL_ID", "").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip() or None,
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip() or None,
        llm_provider=os.getenv("LLM_PROVIDER", "openai").strip().lower(),
        post_time=os.getenv("POST_TIME", "10:00").strip(),
        morning_window=os.getenv("MORNING_WINDOW", "09:00-11:50").strip(),
        evening_window=os.getenv("EVENING_WINDOW", "17:00-21:30").strip(),
        timezone=os.getenv("TIMEZONE", "Europe/Minsk").strip(),
        max_news_age_hours=int(os.getenv("MAX_NEWS_AGE_HOURS", "48")),
        source_cooldown_recent_posts=int(os.getenv("SOURCE_COOLDOWN_RECENT_POSTS", "6")),
        dry_run=_as_bool(os.getenv("DRY_RUN"), default=True),
        moderation_enabled=_as_bool(os.getenv("MODERATION_ENABLED"), default=False),
        moderation_chat_id=os.getenv("MODERATION_CHAT_ID", "").strip(),
        moderation_timeout_minutes=int(os.getenv("MODERATION_TIMEOUT_MINUTES", "120")),
        moderation_choices=max(1, int(os.getenv("MODERATION_CHOICES", "1"))),
        published_file=BASE_DIR / os.getenv("PUBLISHED_FILE", "published.json"),
        blocked_sources_file=BASE_DIR / os.getenv("BLOCKED_SOURCES_FILE", "blocked_sources.json"),
        request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "15")),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip(),
    )
