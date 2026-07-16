from __future__ import annotations

import logging
import re
from typing import Any

from groq import Groq
from openai import OpenAI

from filters import contains_political_text, is_political_news

logger = logging.getLogger(__name__)
MAX_TELEGRAM_PHOTO_CAPTION_LENGTH = 1024


SYSTEM_PROMPT = """Ты редактор русскоязычного Telegram-канала про ИИ, маркетинг, дизайн и технологии.

Сделай короткий пост на русском языке по заголовку и краткому описанию новости.

Главное правило стиля: пиши для живых людей, а не для ML-лаборатории.
Аудитория: junior/middle айтишники, дизайнеры, маркетологи, менеджеры и владельцы малого бизнеса.
Текст должен звучать как нормальная русская короткая новость, а не как перевод с английского пресс-релиза.
Лучший тон: спокойно, ясно, по делу, без канцелярита и без "технологического пафоса".
Представь, что текст читает русскоязычный разработчик, дизайнер или маркетолог в Telegram. Он должен сразу понять: что случилось, кому это полезно и зачем читать дальше.

Нельзя:
- добавлять факты, которых нет в исходных данных;
- писать политический контент;
- использовать грубые слова вроде "сдыхает", "умирает", "ломается в хлам";
- оставлять машинные кальки: "дрифт распределения", "инференс", "sensitivity-анализ", "поддержание моделей", "стоимость поддержания";
- перегружать текст терминами без объяснения;
- делать заголовок длиннее одного предложения;
- писать рекламно, кликбейтно или канцелярски.
- писать фразы вроде "представила новые возможности для работы", "проактивные рабочие процессы", "архитектура продуктов", "пользовательский опыт", если их можно сказать проще;
- использовать слово "управляемые агенты" без пояснения. Лучше: "ИИ-агенты, которым можно поручать задачи".
- писать "может революционизировать", "инновационные AI-продукты", "повысить эффективность разработки программного обеспечения", "гибридные и локальные корпоративные среды". Это звучит не по-русски и рекламно.

Если термин важен, объясни его простыми словами:
- "инференс" -> "работа модели после запуска";
- "дрифт распределения" -> "изменение данных со временем";
- "sensitivity-анализ" -> "проверка, насколько результат зависит от настроек";
- "бенчмарк" -> "тест".

Если новость слишком узкая и её нельзя понятно объяснить обычной аудитории канала, верни LOW_AUDIENCE_VALUE.
Если новость связана с политикой, войной, выборами, санкциями, госрегулированием, армией, полицией или слежкой, верни POLITICAL_CONTENT_REJECTED.

Формат:
Короткий живой заголовок на русском, без двоеточия в стиле пресс-релиза.

2-3 коротких абзаца. Сначала суть события, потом одна-две важные детали и практический смысл для читателя.
Не используй одинаковые рубрики в каждом посте. Не пиши отдельный блок "Почему это важно:".
Пиши конкретно: кто что выпустил/запустил/изменил, кому это пригодится и почему это не просто инфошум.
Пример плохого стиля: "OpenAI и Dell интегрируют Codex в гибридные и локальные корпоративные среды, что может революционизировать разработку ПО".
Пример хорошего стиля: "OpenAI и Dell договорились запускать Codex в инфраструктуре компаний. Это нужно крупным командам: они смогут использовать помощника для кода там, где важны контроль данных и безопасность."

Источник: URL

Весь пост вместе со ссылкой должен быть короче 950 символов."""


USER_INSTRUCTIONS = """Сделай Telegram-пост строго по формату.

Требования к языку:
- простой современный русский;
- без англицизмов, если есть нормальная русская замена;
- без кальки с английского: "продуктовые команды", "проактивные рабочие процессы", "управляемые агенты", "улучшит пользовательский опыт";
- без рекламного пафоса: "революционизирует", "инновационный", "прорывной", "выводит на новый уровень", если этого прямо нет в источнике;
- если речь про AI-агентов, объясни простыми словами: "им можно поручать часть работы", "они помогают писать код", "они сами проходят несколько шагов задачи";
- без фраз "сдыхает", "выживание под дрифтом", "стоимость поддержания", "непрерывный инференс";
- если исходник технический, переведи смысл на человеческий язык;
- не используй шаблонный блок "Почему это важно:";
- не растягивай заголовок;
- не пиши "для разработчиков это значит возможность" — пиши проще: "разработчикам это поможет...";
- не пиши "это показывает, куда движется..." — лучше объясни практическую пользу;
- последняя строка строго: Источник: {url}
"""


BAD_STYLE_REPLACEMENTS = {
    "управляемые агенты": "ИИ-агенты, которым можно поручать задачи",
    "управляемыми агентами": "ИИ-агентами, которым можно поручать задачи",
    "проактивные рабочие процессы": "автоматические сценарии работы",
    "проактивными рабочими процессами": "автоматическими сценариями работы",
    "архитектура продуктов": "устройство цифровых продуктов",
    "архитектуру продуктов": "устройство цифровых продуктов",
    "пользовательский опыт": "опыт пользователей",
    "масштабирование": "рост проектов",
    "агентное будущее": "будущее с ИИ-агентами",
    "может революционизировать": "может заметно изменить",
    "революционизировать": "заметно изменить",
    "инновационные AI-продукты": "новые ИИ-инструменты",
    "инновационные ИИ-продукты": "новые ИИ-инструменты",
    "гибридные и локальные корпоративные среды": "серверы компаний и смешанную инфраструктуру",
    "гибридных и локальных корпоративных средах": "на серверах компаний и в смешанной инфраструктуре",
    "эффективность разработки программного обеспечения": "скорость разработки",
    "разработки программного обеспечения": "разработки",
    "повышая безопасность и эффективность": "делая работу безопаснее и проще",
    "продуктовые команды": "команды, которые развивают продукты",
    "«суперприложение»": "единое приложение",
    "«супер-приложение»": "единое приложение",
    "супер-приложения": "единого приложения",
    "супер-приложение": "единое приложение",
    "суперприложения": "единого приложения",
    "суперприложение": "единое приложение",
    "взаимодействие с пользователями": "работу с пользователями",
    "взаимодействию с пользователями": "работе с пользователями",
    "бенчмарк": "тест",
    "бенчмарка": "теста",
    "бенчмарке": "тесте",
    "выживание под": "устойчивость к",
    "сдыхает": "быстро теряет качество",
    "сдохла": "перестала стабильно работать",
    "сдох": "перестал стабильно работать",
    "дрифт распределения": "изменение данных со временем",
    "дрейф распределения": "изменение данных со временем",
    "инференс": "работа модели после запуска",
    "инференса": "работы модели после запуска",
    "sensitivity-анализ": "проверка зависимости результата от настроек",
    "sensitivity analysis": "проверка зависимости результата от настроек",
    "стоимость поддержания": "стоимость сопровождения",
    "поддержание моделей": "сопровождение моделей",
}

BAD_STYLE_PATTERNS = (
    r"\bunder distribution drift\b",
    r"\bcontinuous inference\b",
    r"\bmaintenance cost\b",
    r"может\s+революционизировать",
    r"гибридн\w+\s+и\s+локальн\w+\s+корпоративн\w+\s+сред",
    r"эффективност\w+\s+разработк\w+\s+программного\s+обеспечения",
    r"инновационн\w+\s+(ai|ии)[-\s]?продукт",
    r"выводит\s+.*\s+на\s+новый\s+уровень",
)


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

    if openai_api_key:
        text = _adapt_with_openai(news, openai_api_key, model)
        if text:
            return text
        logger.warning("OpenAI adaptation failed, falling back to configured provider")

    if llm_provider == "groq" and groq_api_key:
        text = _adapt_with_groq(news, groq_api_key, groq_model)
        if text:
            return text
        logger.warning("Groq adaptation failed, falling back to template")

    return _fallback_post(news)


def _build_user_prompt(news: dict[str, Any]) -> str:
    return f"""Исходные данные новости:
Title: {news.get("title", "")}
Summary: {news.get("summary", "")}
Language: {news.get("language", "")}
Source: {news.get("source_name", "")}
URL: {news.get("url", "")}

{USER_INSTRUCTIONS.format(url=news.get("url", ""))}
"""


def _adapt_with_groq(news: dict[str, Any], groq_api_key: str, model: str) -> str | None:
    client = Groq(api_key=groq_api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(news)},
            ],
            temperature=0.25,
            max_tokens=650,
        )
    except Exception:
        logger.exception("Groq adaptation failed")
        return None

    return _finalize_text(response.choices[0].message.content or "", news, lambda text: _shorten_with_groq(client, text, news, model))


def _adapt_with_openai(news: dict[str, Any], openai_api_key: str, model: str) -> str | None:
    client = OpenAI(api_key=openai_api_key)
    try:
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(news)},
            ],
            temperature=0.25,
            max_output_tokens=650,
        )
    except Exception:
        logger.exception("OpenAI adaptation failed")
        return None

    return _finalize_text(response.output_text or "", news, lambda text: _shorten_with_openai(client, text, news, model))


def _finalize_text(text: str, news: dict[str, Any], shortener) -> str | None:
    text = text.strip()
    if not text or "POLITICAL_CONTENT_REJECTED" in text or "LOW_AUDIENCE_VALUE" in text:
        return None
    if contains_political_text(text):
        logger.warning("Adapted text rejected by political filter: %s", news.get("url"))
        return None

    text = _sanitize_style(text)
    text = _ensure_source_line(text, news)
    text = _normalize_post_shape(text)

    if _has_bad_style(text):
        logger.warning("Adapted text rejected by style filter: %s", news.get("url"))
        return None

    if len(text) > MAX_TELEGRAM_PHOTO_CAPTION_LENGTH:
        text = shortener(text)
        if not text:
            return None
        text = _sanitize_style(_ensure_source_line(text, news))

    if len(text) > MAX_TELEGRAM_PHOTO_CAPTION_LENGTH or contains_political_text(text) or _has_bad_style(text):
        return None
    return text


def _shorten_with_groq(client: Groq, text: str, news: dict[str, Any], model: str) -> str | None:
    prompt = _shorten_prompt(text, news)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Сокращай технологические посты простым русским языком. Не добавляй факты."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.15,
            max_tokens=450,
        )
    except Exception:
        logger.exception("Groq shortening failed")
        return None
    return (response.choices[0].message.content or "").strip()


def _shorten_with_openai(client: OpenAI, text: str, news: dict[str, Any], model: str) -> str | None:
    prompt = _shorten_prompt(text, news)
    try:
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": "Сокращай технологические посты простым русским языком. Не добавляй факты."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.15,
            max_output_tokens=450,
        )
    except Exception:
        logger.exception("OpenAI shortening failed")
        return None
    return (response.output_text or "").strip()


def _shorten_prompt(text: str, news: dict[str, Any]) -> str:
    return f"""Сократи пост до 900 символов вместе со ссылкой.
Сохрани простой русский язык и последнюю строку "Источник: {news.get("url", "")}".
Не добавляй факты.
Убери англицизмы и грубые слова.

Текст:
{text}
"""


def _sanitize_style(text: str) -> str:
    fixed = text
    for bad, good in BAD_STYLE_REPLACEMENTS.items():
        fixed = re.sub(re.escape(bad), good, fixed, flags=re.IGNORECASE)
    fixed = fixed.replace(" - ", " — ")
    fixed = re.sub(r"\n{3,}", "\n\n", fixed)
    return fixed.strip()


def _has_bad_style(text: str) -> bool:
    lowered = text.lower()
    if any(bad in lowered for bad in BAD_STYLE_REPLACEMENTS):
        return True
    return any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in BAD_STYLE_PATTERNS)


def _normalize_post_shape(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    for index, line in enumerate(lines):
        if line.strip():
            lines[index] = _cleanup_title(line)
            break
    text = "\n".join(lines).strip()
    text = re.sub(r"\n\s*Почему это важно:\s*\n", "\n\n", text, flags=re.IGNORECASE)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _improve_why_section(text: str) -> str:
    if "Почему это важно:" not in text:
        return text

    source_match = re.search(r"\n\nИсточник:\s*\S+\s*$", text)
    source = source_match.group(0).strip() if source_match else ""
    without_source = text[: source_match.start()].rstrip() if source_match else text.rstrip()

    before, _, after = without_source.partition("Почему это важно:")
    body_paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", before) if paragraph.strip()]
    why_lines = [line.strip() for line in after.strip().splitlines() if line.strip()]
    current_why = " ".join(why_lines).strip()

    generic_why = {
        "Это помогает понять, какие AI-инструменты уже можно применить в работе.",
        "Это помогает понять, какие ИИ-инструменты уже можно применить в работе.",
        "Это помогает понять, какие технологии могут стать полезными в работе и бизнесе.",
    }
    useful_prefixes = (
        "это поможет", "это упростит", "это удобно", "разработчикам", "компаниям",
        "маркетологам", "дизайнерам", "ит-специалистам", "пользователям",
    )

    if current_why in generic_why and len(body_paragraphs) >= 2:
        candidate = body_paragraphs[-1]
        if candidate.lower().startswith(useful_prefixes) and len(candidate) <= 240:
            body_paragraphs = body_paragraphs[:-1]
            current_why = candidate

    if current_why in generic_why and body_paragraphs:
        title = body_paragraphs[0].lower()
        if "codex" in title or "помощник" in before.lower():
            current_why = "Командам будет проще использовать ИИ-помощника для кода там, где важны контроль данных и безопасность."
        elif "openai" in before.lower() or "chatgpt" in before.lower():
            current_why = "Разработчикам и бизнесу будет проще работать с ИИ-инструментами в одном месте."
        elif "llm" in before.lower() or "языков" in before.lower():
            current_why = "Разработчикам проще понять, какие ИИ-модели уже подходят для реальной работы с кодом и автоматизацией."

    body = "\n\n".join(body_paragraphs).strip()
    result = f"{body}\n\nПочему это важно:\n{current_why}".strip()
    if source:
        result = f"{result}\n\n{source}"
    return result


def _cleanup_title(line: str) -> str:
    title = line.strip()
    if len(title) <= 120:
        return title
    for separator in (". ", ".\n", " — ", ": "):
        position = title.find(separator)
        if 40 <= position <= 120:
            return title[:position].rstrip(".: —")
    return title[:117].rstrip(" ,.;:—-") + "..."


def _ensure_source_line(text: str, news: dict[str, Any]) -> str:
    source_line = f"Источник: {news.get('url')}"
    lines = [line for line in text.splitlines() if not line.strip().lower().startswith("источник:")]
    body = "\n".join(lines).rstrip()
    return f"{body}\n\n{source_line}"


def _fallback_post(news: dict[str, Any]) -> str | None:
    if str(news.get("language") or "").lower() not in {"ru", ""}:
        logger.warning("No LLM key available for foreign news, skipping fallback: %s", news.get("url"))
        return None

    title = (news.get("title") or "Технологическая новость").strip()
    summary = (news.get("summary") or "").strip()
    url = (news.get("url") or "").strip()
    if not url:
        return None

    text = (
        f"{title}\n\n"
        f"{summary[:420].rstrip()}\n\n"
        "Это стоит знать тем, кто следит за ИИ-инструментами, разработкой и digital.\n\n"
        f"Источник: {url}"
    )
    text = _sanitize_style(text)
    if len(text) > MAX_TELEGRAM_PHOTO_CAPTION_LENGTH:
        text = _force_caption_limit(text, news)
    if contains_political_text(text) or _has_bad_style(text):
        return None
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
