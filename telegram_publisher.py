from __future__ import annotations

import logging
import json
from typing import Any
from urllib.parse import urlparse

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

    if image_url and is_image_reachable(image_url, timeout):
        if len(text) > MAX_CAPTION_LENGTH:
            logger.error("Post is too long for Telegram photo caption: %s chars", len(text))
            return False
        if send_photo_with_caption(bot_token, channel_id, text, image_url, timeout):
            return True
        logger.error("Telegram rejected photo publication")
        return False

    return _send_message(bot_token, channel_id, text, timeout)


def send_photo_with_caption(
    bot_token: str,
    channel_id: str,
    caption: str,
    image_url: str,
    timeout: int,
    reply_markup: dict[str, Any] | None = None,
) -> bool:
    if _send_photo_by_url(bot_token, channel_id, caption, image_url, timeout, reply_markup):
        return True
    return _send_photo_by_upload(bot_token, channel_id, caption, image_url, timeout, reply_markup)


def _send_message(bot_token: str, channel_id: str, text: str, timeout: int) -> bool:
    url = TELEGRAM_API.format(token=bot_token, method="sendMessage")
    payload: dict[str, Any] = {
        "chat_id": channel_id,
        "text": text[:MAX_MESSAGE_LENGTH],
        "disable_web_page_preview": False,
    }
    return _post(url, payload, timeout)


def _send_photo_by_url(
    bot_token: str,
    channel_id: str,
    caption: str,
    image_url: str,
    timeout: int,
    reply_markup: dict[str, Any] | None = None,
) -> bool:
    url = TELEGRAM_API.format(token=bot_token, method="sendPhoto")
    payload = {
        "chat_id": channel_id,
        "photo": image_url,
        "caption": caption,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return _post(url, payload, timeout)


def _send_photo_by_upload(
    bot_token: str,
    channel_id: str,
    caption: str,
    image_url: str,
    timeout: int,
    reply_markup: dict[str, Any] | None = None,
) -> bool:
    image = _download_image(image_url, timeout)
    if not image:
        return False

    filename, content, content_type = image
    url = TELEGRAM_API.format(token=bot_token, method="sendPhoto")
    data: dict[str, Any] = {"chat_id": channel_id, "caption": caption}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
    files = {"photo": (filename, content, content_type)}

    try:
        response = requests.post(url, data=data, files=files, timeout=timeout)
        if response.ok:
            logger.info("Telegram photo upload succeeded")
            return True
        logger.error("Telegram photo upload failed: %s %s", response.status_code, response.text)
    except requests.RequestException:
        logger.exception("Telegram photo upload request failed")
    return False


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


def _download_image(image_url: str, timeout: int) -> tuple[str, bytes, str] | None:
    try:
        response = requests.get(image_url, stream=True, allow_redirects=True, timeout=timeout)
        content_type = response.headers.get("content-type", "image/jpeg").split(";")[0]
        if not response.ok or not content_type.startswith("image/"):
            return None
        content = response.content
        if not content:
            return None
    except requests.RequestException:
        logger.warning("Could not download image for upload: %s", image_url)
        return None

    extension = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(content_type, ".jpg")
    path = urlparse(image_url).path
    filename = path.rsplit("/", maxsplit=1)[-1] or f"image{extension}"
    if "." not in filename:
        filename = f"{filename}{extension}"
    return filename, content, content_type


def is_image_reachable(image_url: str, timeout: int) -> bool:
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
