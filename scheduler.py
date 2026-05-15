from __future__ import annotations

from datetime import datetime, timedelta
import logging
import random

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.date import DateTrigger
from zoneinfo import ZoneInfo

from config import Settings

logger = logging.getLogger(__name__)


def run_daily(settings: Settings, job) -> None:
    scheduler = BlockingScheduler(timezone=ZoneInfo(settings.timezone))
    timezone = ZoneInfo(settings.timezone)

    def schedule_next_day_posts() -> None:
        now = datetime.now(timezone)
        _schedule_random_post(
            scheduler=scheduler,
            job=job,
            window=settings.morning_window,
            timezone=timezone,
            now=now,
            job_id="daily_morning_post",
        )
        _schedule_random_post(
            scheduler=scheduler,
            job=job,
            window=settings.evening_window,
            timezone=timezone,
            now=now,
            job_id="daily_evening_post",
        )

    schedule_next_day_posts()
    scheduler.add_job(schedule_next_day_posts, "cron", hour=0, minute=5, id="plan_daily_random_posts")
    logger.info(
        "Scheduler started. Random windows: morning=%s, evening=%s, timezone=%s",
        settings.morning_window,
        settings.evening_window,
        settings.timezone,
    )
    scheduler.start()


def _schedule_random_post(scheduler: BlockingScheduler, job, window: str, timezone: ZoneInfo, now: datetime, job_id: str) -> None:
    start_time, end_time = _parse_window(window)
    target_date = now.date()
    run_at = _random_datetime_in_window(target_date, start_time, end_time, timezone)
    if run_at <= now + timedelta(minutes=2):
        run_at = _random_datetime_in_window(target_date + timedelta(days=1), start_time, end_time, timezone)

    scheduler.add_job(
        job,
        trigger=DateTrigger(run_date=run_at),
        id=job_id,
        replace_existing=True,
        misfire_grace_time=1800,
    )
    logger.info("Scheduled %s at %s", job_id, run_at.isoformat())


def _parse_window(value: str) -> tuple[tuple[int, int], tuple[int, int]]:
    if "-" not in value:
        raise ValueError("Window must be in HH:MM-HH:MM format")
    start_raw, end_raw = value.split("-", maxsplit=1)
    start = _parse_post_time(start_raw.strip())
    end = _parse_post_time(end_raw.strip())
    if start >= end:
        raise ValueError("Window start must be earlier than window end")
    return start, end


def _parse_post_time(value: str) -> tuple[int, int]:
    try:
        hour_raw, minute_raw = value.split(":", maxsplit=1)
        hour = int(hour_raw)
        minute = int(minute_raw)
    except ValueError as exc:
        raise ValueError("POST_TIME must be in HH:MM format") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("POST_TIME must be a valid time in HH:MM format")
    return hour, minute


def _random_datetime_in_window(
    target_date,
    start_time: tuple[int, int],
    end_time: tuple[int, int],
    timezone: ZoneInfo,
) -> datetime:
    start_dt = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        start_time[0],
        start_time[1],
        tzinfo=timezone,
    )
    end_dt = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        end_time[0],
        end_time[1],
        tzinfo=timezone,
    )
    total_seconds = int((end_dt - start_dt).total_seconds())
    offset = random.randint(0, total_seconds)
    return start_dt + timedelta(seconds=offset)
