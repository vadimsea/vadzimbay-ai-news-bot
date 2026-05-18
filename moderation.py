from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging
import time
from typing import Any

import requests

from telegram_publisher import MAX_CAPTION_LENGTH, is_image_reachable, send_photo_with_caption

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


@dataclass(frozen=True)
class ModerationResult:
    approved: bool
    reason: str


@dataclass(frozen=True)
class ModerationItem:
    text: str
    news: dict[str, Any]
    image_url: str | None


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


def request_moderation_batch(
    bot_token: str,
    moderation_chat_id: str,
    items: list[ModerationItem],
    timeout_minutes: int,
    request_timeout: int = 15,
) -> list[ModerationResult]:
    if not moderation_chat_id:
        return [ModerationResult(False, "MODERATION_CHAT_ID is empty") for _ in items]

    tokens: list[str] = []
    token_indexes: dict[str, int] = {}
    results: list[ModerationResult] = []
    for index, item in enumerate(items, start=1):
        token = _make_token(item.news)
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": f"Опубликовать {index}", "callback_data": f"approve:{token}"},
                    {"text": f"Отклонить {index}", "callback_data": f"reject:{token}"},
                ]
            ]
        }
        sent = _send_moderation_preview(
            bot_token=bot_token,
            chat_id=moderation_chat_id,
            text=item.text,
            image_url=item.image_url,
            reply_markup=reply_markup,
            timeout=request_timeout,
        )
        if sent:
            tokens.append(token)
            token_indexes[token] = index - 1
        results.append(ModerationResult(False, "pending" if sent else "Could not send moderation preview"))

    if not tokens:
        return results

    logger.info("Moderation batch sent: %s item(s). Waiting up to %s minutes", len(items), timeout_minutes)
    decisions = _wait_for_batch_decisions(
        bot_token=bot_token,
        tokens=tokens,
        timeout_minutes=timeout_minutes,
        request_timeout=request_timeout,
    )
    for token, decision in decisions.items():
        results[token_indexes[token]] = decision
    return results


def _send_moderation_preview(
    bot_token: str,
    chat_id: str,
    text: str,
    image_url: str | None,
    reply_markup: dict[str, Any],
    timeout: int,
) -> bool:
    if image_url and len(text) <= MAX_CAPTION_LENGTH and is_image_reachable(image_url, timeout):
        return send_photo_with_caption(
            bot_token=bot_token,
            channel_id=chat_id,
            caption=text,
            image_url=image_url,
            timeout=timeout,
            reply_markup=reply_markup,
        )

    url = TELEGRAM_API.format(token=bot_token, method="sendMessage")
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
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
            message = callback.get("message") or {}

            if data == f"approve:{token}":
                _answer_callback(bot_token, callback_id, "Публикую")
                _mark_moderation_message(bot_token, message, "✅ Выбрано к публикации")
                return ModerationResult(True, "approved")
            if data == f"reject:{token}":
                _answer_callback(bot_token, callback_id, "Отклонено")
                _mark_moderation_message(bot_token, message, "❌ Отклонено")
                return ModerationResult(False, "rejected")

        time.sleep(5)

    return ModerationResult(False, "moderation timeout")


def _wait_for_batch_decisions(
    bot_token: str,
    tokens: list[str],
    timeout_minutes: int,
    request_timeout: int,
) -> dict[str, ModerationResult]:
    pending = set(tokens)
    decisions: dict[str, ModerationResult] = {}
    deadline = time.monotonic() + max(1, timeout_minutes) * 60
    offset: int | None = None

    while pending and time.monotonic() < deadline:
        updates = _get_updates(bot_token, offset, request_timeout)
        for update in updates:
            offset = update["update_id"] + 1
            callback = update.get("callback_query") or {}
            data = callback.get("data") or ""
            callback_id = callback.get("id")
            message = callback.get("message") or {}

            for token in list(pending):
                if data == f"approve:{token}":
                    _answer_callback(bot_token, callback_id, "Публикую")
                    _mark_moderation_message(bot_token, message, "✅ Выбрано к публикации")
                    decisions[token] = ModerationResult(True, "approved")
                    pending.remove(token)
                    for skipped_token in pending:
                        decisions[skipped_token] = ModerationResult(False, "skipped_after_approval")
                    return decisions
                if data == f"reject:{token}":
                    _answer_callback(bot_token, callback_id, "Отклонено")
                    _mark_moderation_message(bot_token, message, "❌ Отклонено")
                    decisions[token] = ModerationResult(False, "rejected")
                    pending.remove(token)
                    break

        time.sleep(5)

    for token in pending:
        decisions[token] = ModerationResult(False, "moderation timeout")
    return decisions


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


def _mark_moderation_message(bot_token: str, message: dict[str, Any], status_text: str) -> None:
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    message_id = message.get("message_id")
    if not chat_id or not message_id:
        return

    _remove_inline_keyboard(bot_token, chat_id, message_id)

    caption = message.get("caption")
    text = message.get("text")
    if caption is not None:
        _edit_message_caption(bot_token, chat_id, message_id, caption, status_text)
    elif text is not None:
        _edit_message_text(bot_token, chat_id, message_id, text, status_text)


def _remove_inline_keyboard(bot_token: str, chat_id: int | str, message_id: int) -> None:
    url = TELEGRAM_API.format(token=bot_token, method="editMessageReplyMarkup")
    payload = {"chat_id": chat_id, "message_id": message_id, "reply_markup": {"inline_keyboard": []}}
    try:
        requests.post(url, json=payload, timeout=10)
    except requests.RequestException:
        logger.debug("Could not remove moderation buttons", exc_info=True)


def _edit_message_caption(
    bot_token: str,
    chat_id: int | str,
    message_id: int,
    caption: str,
    status_text: str,
) -> None:
    updated = _append_status(caption, status_text, MAX_CAPTION_LENGTH)
    url = TELEGRAM_API.format(token=bot_token, method="editMessageCaption")
    payload = {"chat_id": chat_id, "message_id": message_id, "caption": updated, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if not response.ok:
            logger.debug("Could not edit moderation caption: %s %s", response.status_code, response.text)
    except requests.RequestException:
        logger.debug("Could not edit moderation caption", exc_info=True)


def _edit_message_text(
    bot_token: str,
    chat_id: int | str,
    message_id: int,
    text: str,
    status_text: str,
) -> None:
    updated = _append_status(text, status_text, 4096)
    url = TELEGRAM_API.format(token=bot_token, method="editMessageText")
    payload = {"chat_id": chat_id, "message_id": message_id, "text": updated, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if not response.ok:
            logger.debug("Could not edit moderation text: %s %s", response.status_code, response.text)
    except requests.RequestException:
        logger.debug("Could not edit moderation text", exc_info=True)


def _append_status(text: str, status_text: str, limit: int) -> str:
    marker = "\n\n" + status_text
    if status_text in text:
        return text[:limit]
    available = limit - len(marker)
    if available <= 0:
        return status_text[:limit]
    return text[:available].rstrip() + marker


def _make_token(news: dict[str, Any]) -> str:
    value = str(news.get("url") or news.get("title") or time.time())
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
