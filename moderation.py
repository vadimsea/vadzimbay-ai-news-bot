from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging
import time
from typing import Any

import requests

from telegram_publisher import MAX_CAPTION_LENGTH, publish_to_telegram

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


@dataclass(frozen=True)
class ModerationResult:
    approved: bool
    reason: str


def request_moderation(
    bot_token: str,
    moderation_chat_id: str,
    text: str,
    news: dict[str, Any],
    image_url: str | None,
    timeout_minutes: int,
    request_timeout: int = 15,
) -> ModerationResult:
    if not moderation_chat_id:
        return ModerationResult(False, "MODERATION_CHAT_ID is empty")

    token = _make_token(news)
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "Опубликовать", "callback_data": f"approve:{token}"},
                {"text": "Отклонить", "callback_data": f"reject:{token}"},
            ]
        ]
    }

    sent = _send_moderation_preview(
        bot_token=bot_token,
        chat_id=moderation_chat_id,
        text=text,
        image_url=image_url,
        reply_markup=reply_markup,
        timeout=request_timeout,
    )
    if not sent:
        return ModerationResult(False, "Could not send moderation preview")

    logger.info("Moderation preview sent. Waiting up to %s minutes", timeout_minutes)
    return _wait_for_decision(
        bot_token=bot_token,
        token=token,
        timeout_minutes=timeout_minutes,
        request_timeout=request_timeout,
    )


def _send_moderation_preview(
    bot_token: str,
    chat_id: str,
    text: str,
    image_url: str | None,
    reply_markup: dict[str, Any],
    timeout: int,
) -> bool:
    if image_url and len(text) <= MAX_CAPTION_LENGTH:
        url = TELEGRAM_API.format(token=bot_token, method="sendPhoto")
        payload = {
            "chat_id": chat_id,
            "photo": image_url,
            "caption": text,
            "reply_markup": reply_markup,
        }
    else:
        url = TELEGRAM_API.format(token=bot_token, method="sendMessage")
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": False,
            "reply_markup": reply_markup,
        }

    try:
        response = requests.post(url, json=payload, timeout=timeout)
        if response.ok:
            return True
        logger.error("Moderation preview failed: %s %s", response.status_code, response.text)
    except requests.RequestException:
        logger.exception("Moderation preview request failed")
    return False


def _wait_for_decision(
    bot_token: str,
    token: str,
    timeout_minutes: int,
    request_timeout: int,
) -> ModerationResult:
    deadline = time.monotonic() + max(1, timeout_minutes) * 60
    offset: int | None = None

    while time.monotonic() < deadline:
        updates = _get_updates(bot_token, offset, request_timeout)
        for update in updates:
            offset = update["update_id"] + 1
            callback = update.get("callback_query") or {}
            data = callback.get("data") or ""
            callback_id = callback.get("id")

            if data == f"approve:{token}":
                _answer_callback(bot_token, callback_id, "Публикую")
                return ModerationResult(True, "approved")
            if data == f"reject:{token}":
                _answer_callback(bot_token, callback_id, "Отклонено")
                return ModerationResult(False, "rejected")

        time.sleep(5)

    return ModerationResult(False, "moderation timeout")


def _get_updates(bot_token: str, offset: int | None, timeout: int) -> list[dict[str, Any]]:
    url = TELEGRAM_API.format(token=bot_token, method="getUpdates")
    payload: dict[str, Any] = {"timeout": 10, "allowed_updates": ["callback_query"]}
    if offset is not None:
        payload["offset"] = offset
    try:
        response = requests.post(url, json=payload, timeout=timeout + 15)
        if response.ok:
            data = response.json()
            return data.get("result", []) if data.get("ok") else []
        logger.warning("getUpdates failed: %s %s", response.status_code, response.text)
    except requests.RequestException:
        logger.exception("getUpdates request failed")
    return []


def _answer_callback(bot_token: str, callback_id: str | None, text: str) -> None:
    if not callback_id:
        return
    url = TELEGRAM_API.format(token=bot_token, method="answerCallbackQuery")
    try:
        requests.post(url, json={"callback_query_id": callback_id, "text": text}, timeout=10)
    except requests.RequestException:
        logger.debug("Could not answer callback query", exc_info=True)


def _make_token(news: dict[str, Any]) -> str:
    value = str(news.get("url") or news.get("title") or time.time())
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
