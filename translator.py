from __future__ import annotations

import logging
from typing import Any

from groq import Groq
from openai import OpenAI

from filters import contains_political_text, is_political_news

logger = logging.getLogger(__name__)
MAX_TELEGRAM_PHOTO_CAPTION_LENGTH = 1024


SYSTEM_PROMPT = """Ты редактор Telegram-канала о технологиях.
На основе заголовка и краткого описания новости сделай короткий пост на русском языке.
Не добавляй факты, которых нет в исходных данных.
Не пиши политический контент.
Если новость связана с политикой, войной, выборами, санкциями, государственным регулированием, армией, полицией или слежкой — верни POLITICAL_CONTENT_REJECTED.
Пост должен быть интересным, понятным и коротким.
Весь пост вместе со строкой источника должен быть не длиннее 950 символов.
Не выбирай сухой корпоративный стиль. Объясняй простыми словами, почему это может быть интересно обычному читателю технологического канала.

Формат:
Заголовок новости на русском

Краткий пересказ новости в 2–4 абзаца.

Почему это важно:
1–2 предложения о значении новости для технологий, бизнеса, науки или будущего.

Источник: URL
"""


def adapt_news_to_russian(
    news: dict[str, Any],
    openai_api_key: str | None,
    model: str,
    llm_provider: str = "openai",
    groq_api_key: str | None = None,
    groq_model: str = "llama-3.3-70b-versatile",
) -> str | None:
    if is_political_news(news):
        logger.warning("Translator rejected political source news: %s", news.get("url"))
        return None

    if llm_provider == "groq" and groq_api_key:
        text = _adapt_with_groq(news, groq_api_key, groq_model)
        if text:
            return text
        logger.warning("Groq adaptation failed, falling back to OpenAI")

    if openai_api_key:
        return _adapt_with_openai(news, openai_api_key, model)

    return _fallback_post(news)


def _adapt_with_groq(news: dict[str, Any], groq_api_key: str, model: str) -> str | None:
    client = Groq(api_key=groq_api_key)
    user_prompt = f"""Исходные данные новости:
Title: {news.get("title", "")}
Summary: {news.get("summary", "")}
Language: {news.get("language", "")}
Source: {news.get("source_name", "")}
URL: {news.get("url", "")}

Сделай Telegram-пост строго по формату. Не используй кликбейт и фразы вроде "меняет правила игры", если это не нейтральная формулировка из исходных данных.
Весь пост должен быть короче 950 символов вместе с URL источника, чтобы поместиться в подпись к фото Telegram.
Пиши живо, но спокойно: без канцелярита, без рекламного тона, без скучного пересказа пресс-релиза.
Блок "Почему это важно:" должен быть отдельной строкой.
Последняя строка должна быть: Источник: {news.get("url", "")}
"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.35,
            max_tokens=700,
        )
    except Exception:
        logger.exception("Groq adaptation failed")
        return None

    text = (response.choices[0].message.content or "").strip()
    if not text or "POLITICAL_CONTENT_REJECTED" in text:
        return None
    if contains_political_text(text):
        logger.warning("Groq text rejected by political filter: %s", news.get("url"))
        return None
    text = _ensure_source_line(text, news)
    if len(text) > MAX_TELEGRAM_PHOTO_CAPTION_LENGTH:
        text = _shorten_with_groq(client, text, news, model)
        if not text:
            return None
    return text


def _shorten_with_groq(client: Groq, text: str, news: dict[str, Any], model: str) -> str | None:
    source_line = f"Источник: {news.get('url', '')}"
    target_total = min(880, MAX_TELEGRAM_PHOTO_CAPTION_LENGTH - 40)
    target_body = max(420, target_total - len(source_line) - 4)
    prompt = f"""Сократи этот Telegram-пост так, чтобы весь результат был максимум {target_total} символов.
Текст до строки источника должен быть максимум {target_body} символов.
Нельзя добавлять новые факты. Нельзя менять смысл. Нельзя убирать строку источника.
Сохрани формат:
Заголовок

1 короткий абзац

Почему это важно:
1 короткое предложение.

Источник: {news.get("url", "")}

Текст:
{text}
"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Ты аккуратно сокращаешь Telegram-посты о технологиях."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=500,
        )
    except Exception:
        logger.exception("Groq shortening failed")
        return None

    shortened = _ensure_source_line((response.choices[0].message.content or "").strip(), news)
    if not shortened or contains_political_text(shortened):
        return None
    if len(shortened) > MAX_TELEGRAM_PHOTO_CAPTION_LENGTH:
        shortened = _force_caption_limit(shortened, news)
    return shortened if len(shortened) <= MAX_TELEGRAM_PHOTO_CAPTION_LENGTH else None


def _adapt_with_openai(news: dict[str, Any], openai_api_key: str, model: str) -> str | None:
    client = OpenAI(api_key=openai_api_key)
    user_prompt = f"""Исходные данные новости:
Title: {news.get("title", "")}
Summary: {news.get("summary", "")}
Language: {news.get("language", "")}
Source: {news.get("source_name", "")}
URL: {news.get("url", "")}

Сделай Telegram-пост строго по формату. Не используй кликбейт и фразы вроде "меняет правила игры", если это не нейтральная формулировка из исходных данных.
Весь пост должен быть короче 950 символов вместе с URL источника, чтобы поместиться в подпись к фото Telegram.
Пиши живо, но спокойно: без канцелярита, без рекламного тона, без скучного пересказа пресс-релиза.
Блок "Почему это важно:" должен быть отдельной строкой.
Последняя строка должна быть: Источник: {news.get("url", "")}
"""

    try:
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_output_tokens=700,
        )
    except Exception:
        logger.exception("OpenAI adaptation failed")
        return None

    text = (response.output_text or "").strip()
    if not text or "POLITICAL_CONTENT_REJECTED" in text:
        return None
    if contains_political_text(text):
        logger.warning("Adapted text rejected by political filter: %s", news.get("url"))
        return None
    text = _ensure_source_line(text, news)
    if len(text) > MAX_TELEGRAM_PHOTO_CAPTION_LENGTH:
        text = _shorten_with_openai(client, text, news, model)
        if not text:
            return None
    return text


def _shorten_with_openai(client: OpenAI, text: str, news: dict[str, Any], model: str) -> str | None:
    source_line = f"Источник: {news.get('url', '')}"
    max_total = MAX_TELEGRAM_PHOTO_CAPTION_LENGTH
    target_total = min(880, max_total - 40)
    target_body = max(420, target_total - len(source_line) - 4)
    prompt = f"""Сократи этот Telegram-пост так, чтобы весь результат был максимум {target_total} символов.
Текст до строки источника должен быть максимум {target_body} символов.
Нельзя добавлять новые факты. Нельзя менять смысл. Нельзя убирать строку источника.
Сохрани формат:
Заголовок

1 короткий абзац

Почему это важно:
1 короткое предложение.

Источник: {news.get("url", "")}

Текст:
{text}
"""
    try:
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": "Ты аккуратно сокращаешь Telegram-посты о технологиях."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_output_tokens=500,
        )
    except Exception:
        logger.exception("OpenAI shortening failed")
        return None

    shortened = _ensure_source_line((response.output_text or "").strip(), news)
    if not shortened or "POLITICAL_CONTENT_REJECTED" in shortened:
        return None
    if contains_political_text(shortened):
        return None
    if len(shortened) > MAX_TELEGRAM_PHOTO_CAPTION_LENGTH:
        shortened = _force_caption_limit(shortened, news)
    if len(shortened) > MAX_TELEGRAM_PHOTO_CAPTION_LENGTH:
        logger.warning("Shortened text is still too long for Telegram photo caption: %s chars", len(shortened))
        return None
    return shortened


def _ensure_source_line(text: str, news: dict[str, Any]) -> str:
    source_line = f"Источник: {news.get('url')}"
    if source_line not in text:
        return f"{text.rstrip()}\n\n{source_line}"
    return text


def _force_caption_limit(text: str, news: dict[str, Any]) -> str:
    source_line = f"Источник: {news.get('url')}"
    body = text.replace(source_line, "").strip()
    available = MAX_TELEGRAM_PHOTO_CAPTION_LENGTH - len(source_line) - 4
    if available < 120:
        return source_line

    body = body[:available].rstrip()
    sentence_end = max(body.rfind("."), body.rfind("!"), body.rfind("?"))
    if sentence_end > 80:
        body = body[: sentence_end + 1]
    else:
        body = body.rstrip(".,;:") + "..."
    return f"{body}\n\n{source_line}"


def _fallback_post(news: dict[str, Any]) -> str | None:
    title = (news.get("title") or "Технологическая новость").strip()
    summary = (news.get("summary") or "").strip()
    url = (news.get("url") or "").strip()
    if not url:
        return None

    summary_text = summary if summary else "Источник сообщает о свежем событии в сфере технологий."
    source_line = f"Источник: {url}"
    fixed_text = (
        f"🚀 {title}\n\n"
        "\n\nПочему это важно:\n"
        "Это событие показывает, как развиваются ИИ и цифровые инструменты.\n\n"
        f"{source_line}"
    )
    max_summary_len = max(120, MAX_TELEGRAM_PHOTO_CAPTION_LENGTH - len(fixed_text) - 20)
    if len(summary_text) > max_summary_len:
        summary_text = summary_text[: max_summary_len - 3].rstrip() + "..."

    text = (
        f"🚀 {title}\n\n"
        f"{summary_text}\n\n"
        "Почему это важно:\n"
        "Это показывает, как быстро развиваются ИИ, робототехника и цифровые продукты, "
        "которые могут влиять на бизнес, науку и повседневные инструменты.\n\n"
        f"{source_line}"
    )
    if len(text) > MAX_TELEGRAM_PHOTO_CAPTION_LENGTH:
        text = _compact_fallback_post(title, url)
    if contains_political_text(text):
        return None
    return text


def _compact_fallback_post(title: str, url: str) -> str:
    title_limit = 180
    if len(title) > title_limit:
        title = title[: title_limit - 3].rstrip() + "..."
    return (
        f"{title}\n\n"
        "Короткая технологическая новость из свежего источника. Подробности доступны по ссылке.\n\n"
        "Почему это важно:\n"
        "Такие события помогают отслеживать развитие ИИ, автоматизации и цифровых продуктов.\n\n"
        f"Источник: {url}"
    )
