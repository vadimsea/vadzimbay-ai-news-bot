from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
MAX_CAPTION_LENGTH = 1024
MAX_MESSAGE_LENGTH = 4096
CAPTION_SOURCE_PREFIX = "Источник: "


def publish_to_telegram(
    bot_token: str,
    channel_id: str,
    text: str,
    image_url: str | None = None,
    timeout: int = 15,
) -> bool:
    if not bot_token or not channel_id:
        logger.error("Telegram credentials are missing")
        return False

    if image_url and _image_is_reachable(image_url, timeout):
        if len(text) > MAX_CAPTION_LENGTH:
            logger.error("Post is too long for Telegram photo caption: %s chars", len(text))
            return False
        sent_photo = _send_photo(bot_token, channel_id, text, image_url, timeout)
        if sent_photo:
            return True

    return _send_message(bot_token, channel_id, text, timeout)


def _send_message(bot_token: str, channel_id: str, text: str, timeout: int) -> bool:
    url = TELEGRAM_API.format(token=bot_token, method="sendMessage")
    payload: dict[str, Any] = {
        "chat_id": channel_id,
        "text": text[:MAX_MESSAGE_LENGTH],
        "disable_web_page_preview": False,
    }
    return _post(url, payload, timeout)


def _send_photo(bot_token: str, channel_id: str, caption: str, image_url: str, timeout: int) -> bool:
    url = TELEGRAM_API.format(token=bot_token, method="sendPhoto")
    payload = {
        "chat_id": channel_id,
        "photo": image_url,
        "caption": caption,
    }
    return _post(url, payload, timeout)


def _post(url: str, payload: dict[str, Any], timeout: int) -> bool:
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        if response.ok:
            logger.info("Telegram publication succeeded")
            return True
        logger.error("Telegram publication failed: %s %s", response.status_code, response.text)
    except requests.RequestException:
        logger.exception("Telegram request failed")
    return False


def _image_is_reachable(image_url: str, timeout: int) -> bool:
    try:
        response = requests.head(image_url, allow_redirects=True, timeout=timeout)
        content_type = response.headers.get("content-type", "")
        if response.ok and content_type.startswith("image/"):
            return True

        response = requests.get(image_url, stream=True, allow_redirects=True, timeout=timeout)
        content_type = response.headers.get("content-type", "")
        return response.ok and content_type.startswith("image/")
    except requests.RequestException:
        logger.warning("Image is not reachable: %s", image_url)
        return False

