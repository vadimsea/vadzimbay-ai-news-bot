from __future__ import annotations

import json
import logging
from typing import Any

from groq import Groq
from openai import OpenAI

logger = logging.getLogger(__name__)


RANKING_SYSTEM_PROMPT = """Ты строгий редактор Telegram-канала о технологиях.
Нужно выбрать одну новость, которую действительно интересно опубликовать сегодня.

Запрещено выбирать политику, войны, армии, полицию, санкции, выборы, регулирование, геополитику и идеологические темы.
Если есть сомнение, выбирай другую новость.

Оценивай выше:
- новые AI-модели, роботов, гаджеты, сильные исследования;
- AI для бизнеса, дизайна, маркетинга, образования, медицины и программирования;
- вайбкодинг, coding agents, AI-инструменты для разработки;
- новости с понятной пользой или вау-эффектом для широкой аудитории;
- зарубежные новости, которые можно интересно пересказать на русском.

Оценивай ниже:
- сухие SDK/changelog/API-релизы без понятной пользы;
- узкие бенчмарки и внутренние обновления продуктов;
- корпоративные пресс-релизы без события;
- скучные материалы, которые не хочется переслать.

Ответь только JSON:
{
  "selected_index": 0,
  "reason": "короткая причина выбора",
  "scores": [
    {"index": 0, "wow": 1, "usefulness": 1, "broad_interest": 1, "risk": 0}
  ]
}
"""


def select_best_news_with_llm(
    candidates: list[dict[str, Any]],
    llm_provider: str,
    groq_api_key: str | None,
    groq_model: str,
    openai_api_key: str | None,
    openai_model: str,
) -> tuple[dict[str, Any] | None, str]:
    if not candidates:
        return None, ""

    payload = _build_payload(candidates)
    if llm_provider == "groq" and groq_api_key:
        selected, reason = _select_with_groq(payload, candidates, groq_api_key, groq_model)
        if selected:
            return selected, reason
        logger.warning("Groq LLM ranking failed, falling back to OpenAI")

    if openai_api_key:
        return _select_with_openai(payload, candidates, openai_api_key, openai_model)

    return None, ""


def _build_payload(candidates: list[dict[str, Any]]) -> str:
    compact_items: list[dict[str, Any]] = []
    for index, news in enumerate(candidates):
        compact_items.append(
            {
                "index": index,
                "title": news.get("title", "")[:300],
                "summary": news.get("summary", "")[:700],
                "source": news.get("source_name", ""),
                "language": news.get("language", ""),
                "category": news.get("category", ""),
                "published_at": news.get("published_at", ""),
                "url": news.get("url", ""),
            }
        )
    return json.dumps(compact_items, ensure_ascii=False)


def _select_with_groq(
    payload: str,
    candidates: list[dict[str, Any]],
    api_key: str,
    model: str,
) -> tuple[dict[str, Any] | None, str]:
    client = Groq(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": RANKING_SYSTEM_PROMPT},
                {"role": "user", "content": f"Кандидаты:\n{payload}"},
            ],
            temperature=0.1,
            max_tokens=1200,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""
    except Exception:
        logger.exception("Groq LLM ranking request failed")
        return None, ""

    return _parse_selection(content, candidates)


def _select_with_openai(
    payload: str,
    candidates: list[dict[str, Any]],
    api_key: str,
    model: str,
) -> tuple[dict[str, Any] | None, str]:
    client = OpenAI(api_key=api_key)
    try:
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": RANKING_SYSTEM_PROMPT},
                {"role": "user", "content": f"Кандидаты:\n{payload}"},
            ],
            temperature=0.1,
            max_output_tokens=1200,
        )
        content = response.output_text or ""
    except Exception:
        logger.exception("OpenAI LLM ranking request failed")
        return None, ""

    return _parse_selection(content, candidates)


def _parse_selection(content: str, candidates: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
    try:
        data = json.loads(_extract_json(content))
        selected_index = int(data["selected_index"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        logger.warning("Could not parse LLM ranking response: %s", content[:500])
        return None, ""

    if not 0 <= selected_index < len(candidates):
        return None, ""
    return candidates[selected_index], str(data.get("reason", "llm_selected"))


def _extract_json(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    return stripped
