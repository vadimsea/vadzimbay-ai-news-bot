from __future__ import annotations

import argparse
import logging
from pprint import pformat
import sys

from blocked_sources import filter_allowed_sources, load_blocked_sources
from config import load_settings
from fetcher import extract_article_image_url, fetch_all_news
from filters import contains_political_text
from hashtags import append_hashtags
from llm_ranker import select_best_news_with_llm
from moderation import request_moderation
from post_style import apply_title_emoji
from promo import get_weekly_promo_text
from ranker import choose_best_news
from scheduler import run_daily
from sources import get_sources
from storage import PublishedStorage
from telegram_publisher import is_image_reachable, publish_to_telegram
from translator import adapt_news_to_russian


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")


def run_once() -> bool:
    settings = load_settings()
    storage = PublishedStorage(settings.published_file)
    blocked_sources = load_blocked_sources(settings.blocked_sources_file)
    sources, blocked_source_entries = filter_allowed_sources(get_sources(), blocked_sources)
    if blocked_source_entries:
        logger.warning(
            "Skipped %s blocked source(s): %s",
            len(blocked_source_entries),
            ", ".join(source.name for source in blocked_source_entries),
        )

    logger.info("Processing %s sources", len(sources))
    news_items = fetch_all_news(sources)
    logger.info("Found %s news items", len(news_items))

    def llm_selector(candidates):
        return select_best_news_with_llm(
            candidates=candidates,
            llm_provider=settings.llm_provider,
            groq_api_key=settings.groq_api_key,
            groq_model=settings.groq_model,
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
        )

    selected, stats = choose_best_news(
        news_items=news_items,
        storage=storage,
        blocked_sources=blocked_sources,
        max_age_hours=settings.max_news_age_hours,
        source_cooldown_recent_posts=settings.source_cooldown_recent_posts,
        llm_selector=llm_selector,
    )
    _log_stats(stats, len(sources), len(blocked_source_entries))

    if not selected:
        logger.info("No suitable news found. Nothing will be published.")
        return False

    if selected.get("image_url") and not is_image_reachable(
        selected["image_url"],
        settings.request_timeout_seconds,
    ):
        logger.info("RSS image is not usable, trying to extract image from article page")
        selected["image_url"] = ""

    if not selected.get("image_url"):
        selected["image_url"] = extract_article_image_url(selected["url"])
        if selected.get("image_url"):
            logger.info("Article image found on source page: %s", selected["image_url"])
        else:
            logger.info("No article image found for selected news")

    if not selected.get("image_url") or not is_image_reachable(
        selected["image_url"],
        settings.request_timeout_seconds,
    ):
        logger.info("Selected news has no valid image. Nothing will be published.")
        return False

    post_text = adapt_news_to_russian(
        selected,
        openai_api_key=settings.openai_api_key,
        model=settings.openai_model,
        llm_provider=settings.llm_provider,
        groq_api_key=settings.groq_api_key,
        groq_model=settings.groq_model,
    )
    if not post_text:
        logger.info("Selected news was rejected during adaptation. Nothing will be published.")
        return False

    if contains_political_text(post_text):
        logger.warning("Final post rejected by political filter. Nothing will be published.")
        return False

    if f"Источник: {selected['url']}" not in post_text:
        logger.warning("Final post has no source URL. Nothing will be published.")
        return False
    post_text = apply_title_emoji(post_text, selected)
    post_text = append_hashtags(post_text, selected)

    if settings.dry_run:
        _print_dry_run(selected, stats.get("selected_reason", ""), post_text)
        return True

    if settings.moderation_enabled:
        moderation = request_moderation(
            bot_token=settings.telegram_bot_token,
            moderation_chat_id=settings.moderation_chat_id,
            text=post_text,
            news=selected,
            image_url=selected.get("image_url"),
            timeout_minutes=settings.moderation_timeout_minutes,
            request_timeout=settings.request_timeout_seconds,
        )
        logger.info("Moderation result: %s", moderation.reason)
        if not moderation.approved:
            return False

    published = publish_to_telegram(
        bot_token=settings.telegram_bot_token,
        channel_id=settings.telegram_channel_id,
        text=post_text,
        image_url=selected.get("image_url"),
        timeout=settings.request_timeout_seconds,
    )
    if published:
        storage.mark_as_published(
            selected["url"],
            {
                "title": selected.get("title"),
                "source_name": selected.get("source_name"),
                "published_at": selected.get("published_at"),
            },
        )
    return published


def run_promo_once() -> bool:
    settings = load_settings()
    text = get_weekly_promo_text()

    if settings.dry_run:
        print("\n=== DRY RUN: WEEKLY PROMO ===")
        print(text)
        return True

    published = publish_to_telegram(
        bot_token=settings.telegram_bot_token,
        channel_id=settings.telegram_channel_id,
        text=text,
        image_url=None,
        timeout=settings.request_timeout_seconds,
    )
    if published:
        logger.info("Weekly promo publication succeeded")
    return published


def _log_stats(stats: dict, source_count: int, blocked_source_count: int) -> None:
    logger.info("Sources processed: %s", source_count)
    logger.info("Sources skipped by blocked list: %s", blocked_source_count)
    logger.info("News found: %s", stats.get("total", 0))
    logger.info("Rejected without required fields: %s", stats.get("missing_required_fields", 0))
    logger.info("Rejected as old: %s", stats.get("old", 0))
    logger.info("Rejected as duplicates: %s", stats.get("duplicates", 0))
    logger.info("Rejected by blocked source list: %s", stats.get("blocked_sources", 0))
    logger.info("Rejected by source cooldown: %s", stats.get("source_cooldown", 0))
    logger.info("Rejected as irrelevant: %s", stats.get("irrelevant", 0))
    logger.info("Rejected as low news value: %s", stats.get("low_news_value", 0))
    logger.info("Rejected as politics/war/geopolitics: %s", stats.get("political", 0))
    logger.info("Candidates after filters: %s", stats.get("candidates", 0))


def _print_dry_run(selected: dict, reason: str, post_text: str) -> None:
    print("\n=== DRY RUN: SELECTED NEWS ===")
    print(pformat(selected, sort_dicts=False))
    print("\n=== REASON ===")
    print(reason)
    print("\n=== FINAL TELEGRAM POST ===")
    print(post_text)
    print("\n=== SOURCE ===")
    print(selected.get("url"))
    print("\n=== IMAGE_URL ===")
    print(selected.get("image_url") or "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Vadzimbay Telegram tech news bot")
    parser.add_argument("--once", action="store_true", help="Run one news cycle now")
    parser.add_argument("--promo", action="store_true", help="Publish weekly services promo")
    parser.add_argument("--schedule", action="store_true", help="Run forever with daily schedule")
    args = parser.parse_args()

    if args.promo:
        run_promo_once()
        return

    if args.schedule:
        settings = load_settings()
        run_daily(settings, run_once)
        return

    run_once()


if __name__ == "__main__":
    main()
