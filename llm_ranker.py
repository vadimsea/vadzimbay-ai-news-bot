from __future__ import annotations

import json
import logging
from typing import Any

from groq import Groq
from openai import OpenAI

logger = logging.getLogger(__name__)


RANKING_SYSTEM_PROMPT = """Ты строгий редактор Telegram-канала "ИИ x Маркетинг x Дизайн".

Аудитория: junior/middle айтишники, веб-дизайнеры, frontend-разработчики, маркетологи, продуктовые менеджеры и владельцы малого бизнеса.

Нужно выбрать одну новость, которую реально хочется переслать коллеге. Не выбирай "просто полезное"; нужен эффект: "о, это интересно", "это можно применить", "это показывает куда движется рынок".
Если среди кандидатов нет такой новости, верни selected_index: -1.

Высокий приоритет:
- Новости, которые интересны молодой аудитории: AI для creators, соцсетей, TikTok/Instagram/YouTube, видео, музыки, аватаров, дизайна, мемов, личной продуктивности и инструментов, которые хочется попробовать самому;
- новые AI-модели, заметные релизы OpenAI, Anthropic, Google DeepMind, xAI, Mistral, Meta AI;
- AI-инструменты для кода, vibe coding, coding agents, Cursor, Windsurf, Claude Code, Lovable, Bolt, Replit Agent;
- AI для маркетинга, контента, SEO, рекламы, аналитики и автоматизации продаж;
- AI или новые инструменты для веб-дизайна, UX/UI, Figma, frontend и создания сайтов;
- сильные исследования или продукты, которые понятны не только узким академикам;
- зарубежные новости из авторитетных источников, которые интересно пересказать на русском.

Сильно занижай или не выбирай:
- funding/raises/acquisition/enterprise/B2B/CRM/sales-call news, unless there is a clear consumer, creator, design, social media, marketing, or hands-on tool angle for young people;
- общие UX-статьи, ROI/listicle, "10 фактов", советы, гайды, туториалы;
- dashboard/API/SDK/changelog/minor update без вау-эффекта;
- API-only improvements, speech/transcription benchmarks, "slightly better but worse than competitors", error-rate comparisons without a product people can try;
- cybersecurity/security alliance/AI safety consortium/корпоративная безопасность, если это не прямой инструмент для работы разработчика, дизайнера или маркетолога;
- новости про банки, личные финансы, внутренние корпоративные панели, если это не прорывной AI-продукт;
- обычные роботы/железо/Windows/гаджеты без прямой связи с AI или работой аудитории;
- скучные корпоративные пресс-релизы;
- материалы, которые выглядят как "нормально, но не хочется публиковать".

Запрещено выбирать политику, войны, армии, полицию, санкции, выборы, регулирование, геополитику и госнадзор. Если есть сомнение, не выбирай.

Ответь только JSON:
{
  "selected_index": 0,
  "reason": "коротко: почему это вау/полезно именно для айтишников, дизайнеров, маркетологов или менеджеров",
  "scores": [
    {"index": 0, "wow": 1, "work_usefulness": 1, "audience_fit": 1, "boring_risk": 0}
  ]
}
"""


SCORING_SYSTEM_PROMPT = """Ты строгий редактор Telegram-канала "ИИ x Маркетинг x Дизайн".

Аудитория: junior/middle айтишники, веб-дизайнеры, frontend-разработчики, маркетологи, продуктовые менеджеры и владельцы малого бизнеса, много молодёжи.
Тебе дан список новостей-кандидатов. Оцени КАЖДУЮ по шкале 1-10: захочет ли читатель открыть пост, обсудить его или переслать коллеге.

Шкала:
- 9-10: громкий релиз или событие, о котором завтра будут говорить все; инструмент, который хочется попробовать прямо сейчас;
- 7-8: интересно и понятно нашей аудитории, есть конкретная польза или неожиданный факт;
- 5-6: нормально, но без искры, можно пропустить;
- 1-4: скучно, узко, корпоративно, для исследователей или не по теме.

Повышай оценку: новые модели и заметные релизы OpenAI, Anthropic, Google, xAI, Mistral, Meta; ИИ-инструменты для кода, дизайна, видео, музыки, соцсетей, маркетинга; новости про creators и продукты, которые можно потрогать самому; неожиданные, спорные или забавные истории про ИИ, о которых хочется поговорить. Поле hn_points — сколько очков набрала ссылка на Hacker News: высокое значение (100+) признак живого интереса, но не решает всё.

Понижай оценку: funding/raises/acquisition/enterprise/B2B/CRM без потребительского или творческого угла; гайды, туториалы, listicles, общие рассуждения и эссе; SDK, API, changelog, минорные обновления; бенчмарки и сравнения «чуть лучше/хуже»; корпоративная кибербезопасность; железо и гаджеты без связи с ИИ; скучные пресс-релизы.

Если несколько кандидатов про одно и то же событие (в том числе на разных языках), только самый сильный источник оценивается как обычно, а у остальных в поле duplicate_of указан index сильного кандидата.

Политика, война, армия, полиция, санкции, выборы, регулирование, геополитика: оценка 1.

Ответь только JSON, по одной записи на каждого кандидата, reason не длиннее 12 слов:
{"scores": [{"index": 0, "score": 7, "reason": "...", "duplicate_of": null}]}
"""


def score_news_with_llm(
    candidates: list[dict[str, Any]],
    llm_provider: str,
    groq_api_key: str | None,
    groq_model: str,
    openai_api_key: str | None,
    openai_model: str,
) -> dict[int, tuple[float, str]] | None:
    """Score every candidate 1-10. Returns {candidate index: (score, reason)} or None if no LLM answered."""
    if not candidates:
        return {}

    payload = _build_payload(candidates, summary_chars=400)
    content = ""
    if llm_provider == "groq" and groq_api_key:
        content = _complete_with_groq(SCORING_SYSTEM_PROMPT, payload, groq_api_key, groq_model)
        if not content:
            logger.warning("Groq LLM scoring failed, falling back to OpenAI")
    if not content and openai_api_key:
        content = _complete_with_openai(SCORING_SYSTEM_PROMPT, payload, openai_api_key, openai_model)

    return _parse_scores(content, len(candidates)) if content else None


def _complete_with_groq(system_prompt: str, payload: str, api_key: str, model: str) -> str:
    client = Groq(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Кандидаты:\n{payload}"},
            ],
            temperature=0.1,
            max_tokens=7000,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""
    except Exception:
        logger.exception("Groq LLM scoring request failed")
        return ""


def _complete_with_openai(system_prompt: str, payload: str, api_key: str, model: str) -> str:
    client = OpenAI(api_key=api_key)
    try:
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Кандидаты:\n{payload}"},
            ],
            temperature=0.1,
            max_output_tokens=7000,
        )
        return response.output_text or ""
    except Exception:
        logger.exception("OpenAI LLM scoring request failed")
        return ""


def _parse_scores(content: str, count: int) -> dict[int, tuple[float, str]] | None:
    try:
        data = json.loads(_extract_json(content))
        rows = data["scores"]
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        logger.warning("Could not parse LLM scoring response: %s", content[:500])
        return None

    scores: dict[int, tuple[float, str]] = {}
    for row in rows:
        try:
            index = int(row["index"])
            score = float(row["score"])
        except (KeyError, TypeError, ValueError):
            continue
        if not 0 <= index < count:
            continue
        score = max(1.0, min(10.0, score))
        reason = str(row.get("reason", ""))
        try:
            duplicate_of = int(row.get("duplicate_of"))
        except (TypeError, ValueError):
            duplicate_of = None
        if duplicate_of is not None and duplicate_of != index and 0 <= duplicate_of < count:
            score = min(score, 3.0)
            reason = f"дубль #{duplicate_of}: {reason}"
        scores[index] = (score, reason)
    return scores or None


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


def _build_payload(candidates: list[dict[str, Any]], summary_chars: int = 700) -> str:
    compact_items: list[dict[str, Any]] = []
    for index, news in enumerate(candidates):
        compact_items.append(
            {
                "index": index,
                "title": news.get("title", "")[:300],
                "summary": news.get("summary", "")[:summary_chars],
                "source": news.get("source_name", ""),
                "language": news.get("language", ""),
                "category": news.get("category", ""),
                "published_at": news.get("published_at", ""),
                "url": news.get("url", ""),
                "hn_points": news.get("hn_points", 0),
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
        if selected_index == -1:
            return None, str(data.get("reason", "no_good_news"))
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
