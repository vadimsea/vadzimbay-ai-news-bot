from __future__ import annotations

import argparse
import logging
from pprint import pformat
import sys
from typing import Any
from datetime import datetime
from zoneinfo import ZoneInfo

from blocked_sources import filter_allowed_sources, load_blocked_sources
from config import Settings, load_settings
from fetcher import extract_article_image_url, fetch_all_news
from filters import contains_political_text
from hashtags import append_hashtags
from llm_ranker import select_best_news_with_llm
from moderation import ModerationItem, request_moderation_batch
from post_style import apply_title_emoji
from promo import due_promo_posts, next_promo_hint
from ranker import choose_top_news
from scheduler import run_daily
from sources import get_sources
from storage import PublishedStorage
from telegram_formatting import format_post_html
from telegram_publisher import is_image_reachable, publish_promo_to_telegram, publish_to_telegram
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

    selected_items, stats = choose_top_news(
        news_items=news_items,
        storage=storage,
        blocked_sources=blocked_sources,
        max_age_hours=settings.max_news_age_hours,
        source_cooldown_recent_posts=settings.source_cooldown_recent_posts,
        selection_count=max(settings.moderation_choices * 3, settings.moderation_choices),
        llm_selector=llm_selector,
    )
    _log_stats(stats, len(sources), len(blocked_source_entries))

    if not selected_items:
        logger.info("No suitable news found. Nothing will be published.")
        return False

    prepared_items = _prepare_posts(selected_items, settings, limit=settings.moderation_choices)
    if not prepared_items:
        logger.info("No selected news could be prepared with valid image and safe text.")
        return False

    if settings.dry_run:
        _print_dry_run_batch(prepared_items, stats.get("selected_reasons", []))
        return True

    if settings.moderation_enabled:
        for item in prepared_items:
            storage.mark_as_offered(item.news["url"], _selected_metadata(item.news))
        moderation_results = request_moderation_batch(
            bot_token=settings.telegram_bot_token,
            moderation_chat_id=settings.moderation_chat_id,
            items=prepared_items,
            timeout_minutes=settings.moderation_timeout_minutes,
            request_timeout=settings.request_timeout_seconds,
        )
    else:
        moderation_results = [
            type("Result", (), {"approved": True, "reason": "moderation disabled"})()
            for _ in prepared_items
        ]

    any_published = False
    for item, moderation in zip(prepared_items, moderation_results):
        logger.info("Moderation result for %s: %s", item.news.get("title"), moderation.reason)
        if not moderation.approved:
            if moderation.reason == "rejected":
                storage.mark_as_rejected(item.news["url"], _selected_metadata(item.news))
            continue

        published = publish_to_telegram(
            bot_token=settings.telegram_bot_token,
            channel_id=settings.telegram_channel_id,
            text=item.text,
            image_url=item.image_url,
            timeout=settings.request_timeout_seconds,
        )
        if published:
            any_published = True
            storage.mark_as_published(item.news["url"], _selected_metadata(item.news))
    return any_published


def _prepare_posts(news_items: list[dict[str, Any]], settings: Settings, limit: int) -> list[ModerationItem]:
    prepared: list[ModerationItem] = []
    for selected in news_items:
        if len(prepared) >= limit:
            break

        selected = dict(selected)
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
            logger.info("Selected news has no valid image, skipping: %s", selected.get("title"))
            continue

        post_text = adapt_news_to_russian(
            selected,
            openai_api_key=settings.openai_api_key,
            model=settings.openai_model,
            llm_provider=settings.llm_provider,
            groq_api_key=settings.groq_api_key,
            groq_model=settings.groq_model,
        )
        if not post_text:
            logger.info("Selected news was rejected during adaptation: %s", selected.get("url"))
            continue

        if contains_political_text(post_text):
            logger.warning("Final post rejected by political filter: %s", selected.get("url"))
            continue

        if f"Источник: {selected['url']}" not in post_text:
            logger.warning("Final post has no source URL: %s", selected.get("url"))
            continue

        post_text = apply_title_emoji(post_text, selected)
        post_text = append_hashtags(post_text, selected)
        post_text = format_post_html(post_text)
        prepared.append(
            ModerationItem(
                text=post_text,
                news=selected,
                image_url=selected.get("image_url"),
            )
        )
    return prepared


def _selected_metadata(selected: dict) -> dict:
    return {
        "title": selected.get("title"),
        "source_name": selected.get("source_name"),
        "published_at": selected.get("published_at"),
        "language": selected.get("language"),
    }


def run_promo_once() -> bool:
    settings = load_settings()
    storage = PublishedStorage(settings.published_file)
    timezone = ZoneInfo(settings.timezone)
    now = datetime.now(timezone)
    day = now.date().isoformat()
    posted_keys = storage.promo_keys_posted_for_day(day)
    promos = due_promo_posts(current=now, posted_keys=posted_keys)
    promos = promos[:1]

    if not promos:
        hint = next_promo_hint(current=now, posted_keys=posted_keys)
        logger.info(
            "No promo due now. Current time: %s.%s",
            now.strftime("%Y-%m-%d %H:%M"),
            f" Next promo window: {hint}" if hint else "",
        )
        return False

    any_published = False
    for promo in promos:
        if settings.dry_run:
            print(f"\n=== DRY RUN: PROMO {promo.key} ===")
            print(promo.text)
            print([(button.text, button.url) for button in promo.buttons])
            any_published = True
            continue

        published = publish_promo_to_telegram(
            bot_token=settings.telegram_bot_token,
            channel_id=settings.telegram_channel_id,
            promo=promo,
            timeout=settings.request_timeout_seconds,
        )
        if published:
            any_published = True
            storage.mark_promo_posted(
                promo.key,
                day,
                {"published_at_local": now.isoformat()},
            )
            logger.info("Promo publication succeeded: %s", promo.key)
    return any_published


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
    logger.info("Rejected outside channel priority topics: %s", stats.get("off_topic_priority", 0))
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


def _print_dry_run_batch(items: list[ModerationItem], reasons: list[str]) -> None:
    for index, item in enumerate(items, start=1):
        reason = reasons[index - 1] if index - 1 < len(reasons) else ""
        print(f"\n=== DRY RUN: OPTION {index} ===")
        _print_dry_run(item.news, reason, item.text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Vadzimbay Telegram tech news bot")
    parser.add_argument("--once", action="store_true", help="Run one news cycle now")
    parser.add_argument("--promo", action="store_true", help="Publish scheduled promo")
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
