from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any
from urllib.parse import urlparse


TECH_KEYWORDS = {
    "ai", "artificial intelligence", "machine learning", "deep learning", "llm", "chatgpt",
    "openai", "deepmind", "anthropic", "mistral", "xai", "meta ai", "neural", "neural network",
    "robot", "robotics", "humanoid", "automation", "startup", "gadget", "chip", "semiconductor",
    "gpu", "nvidia", "software", "developer", "programming", "coding", "model", "generative",
    "computer vision", "voice assistant", "wearable", "device", "technology", "tech",
    "web design", "website design", "ui design", "ux design", "design trends", "figma",
    "no-code", "landing page", "creative automation", "marketing ai", "ai marketing",
    "martech", "adtech", "advertising", "content marketing", "seo", "crm",
    "ии", "искусственный интеллект", "нейросеть", "нейросети", "машинное обучение",
    "робот", "робототехника", "автоматизация", "стартап", "гаджет", "чип", "процессор",
    "видеокарта", "технология", "технологии", "нейромодель", "генеративный",
    "веб-дизайн", "веб дизайн", "дизайн сайтов", "ui", "ux", "ux/ui", "тренды дизайна",
    "фигма", "figma", "no-code", "лендинг", "маркетинг", "ии в маркетинге",
    "маркетинговая автоматизация", "реклама", "seo", "crm", "контент-маркетинг",
    "ki", "künstliche intelligenz", "roboter", "robotik", "automatisierung", "technologie",
    "webdesign", "ux design", "ui design", "marketing-ki", "ki-marketing",
}

NEWS_EVENT_KEYWORDS = {
    "launch", "launches", "launched", "release", "released", "announces", "announced",
    "unveils", "introduces", "raises", "funding", "investment", "breakthrough",
    "researchers", "study", "new model", "new robot", "rolls out", "debuts",
    "trend", "trends", "campaign", "tool", "platform",
    "представил", "представила", "представили", "запустил", "запустила", "запустили",
    "выпустил", "выпустила", "выпустили", "анонсировал", "анонсировала", "релиз",
    "инвестиции", "привлек", "привлекла", "раунд", "исследователи", "разработали",
    "создали", "новая модель", "новый робот", "новый гаджет", "обновление",
    "тренд", "тренды", "кампания", "инструмент", "платформа",
    "stellt vor", "startet", "veröffentlicht", "veroeffentlicht", "neues modell",
    "neuer roboter", "finanzierung", "forscher",
}

LOW_NEWS_VALUE_PATTERNS = {
    "what is", "how to", "how does", "explainer", "guide", "tutorial", "tips",
    "что такое", "как работает", "как устроен", "гайд", "инструкция", "руководство",
    "разбор", "подборка", "мнение", "колонка", "личный опыт",
    "was ist", "wie funktioniert", "anleitung", "ratgeber",
}

POLITICAL_STOP_WORDS = {
    "president", "government", "election", "vote", "voting", "parliament", "minister",
    "law", "regulation", "regulator", "regulatory", "ban", "censorship", "sanction",
    "sanctions", "war", "military", "army", "defense", "defence", "drone strike", "police",
    "surveillance", "intelligence agency", "propaganda", "geopolitical", "conflict",
    "weapon", "weapons", "missile", "battlefield", "pentagon", "nato", "white house",
    "congress", "senate", "court", "lawsuit", "export controls", "national security",
    "marxist", "marxism", "socialist", "socialism", "communist", "communism",
    "ideology", "ideological", "political views",
    "президент", "правительство", "выборы", "голосование", "парламент", "министр",
    "министерство", "закон", "законопроект", "регулирование", "регулятор", "запрет",
    "цензура", "санкции", "война", "армия", "военный", "военная", "военные", "оборона",
    "минобороны", "полиция", "слежка", "разведка", "спецслужбы", "пропаганда",
    "геополитика", "конфликт", "оружие", "дрон-камикадзе", "боевые дроны",
    "марксист", "марксизм", "социализм", "социалист", "коммунизм", "коммунист",
    "идеология", "идеологический", "политические взгляды",
    "regierung", "präsident", "praesident", "wahl", "gesetz", "verbot", "krieg",
    "militär", "militaer", "polizei", "überwachung", "ueberwachung", "minister",
    "parlament", "sanktion", "zensur", "marxistisch", "marxistische", "marxismus",
    "sozialismus", "kommunismus", "ideologie", "politische ansichten",
}

POLITICAL_STOP_PHRASES = {
    "ai regulation", "ai law", "military ai", "autonomous weapons", "election interference",
    "facial recognition by police", "government surveillance", "военный ии", "автономное оружие",
    "регулирование ии", "закон об ии", "ии на выборах", "распознавание лиц полицией",
    "государственная слежка", "autonome waffen", "ki-gesetz", "ki regulierung",
    "ki-agenten übernehmen marxistische ansichten", "ai agents adopt political views",
    "ии придерживается политических взглядов",
}


def _combined_text(news: dict[str, Any]) -> str:
    host = urlparse(news.get("url") or "").netloc
    parts = [
        news.get("title") or "",
        news.get("summary") or "",
        news.get("source_name") or "",
        news.get("url") or "",
        host,
    ]
    return " ".join(parts).lower()


def has_required_fields(news: dict[str, Any]) -> bool:
    return bool((news.get("title") or "").strip() and (news.get("url") or "").strip())


def is_recent_news(news: dict[str, Any], max_age_hours: int = 48) -> bool:
    published_at = news.get("published_at")
    if not published_at:
        return False

    try:
        dt = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
    except ValueError:
        return False

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    return now - timedelta(hours=max_age_hours) <= dt <= now + timedelta(hours=2)


def is_relevant_tech_news(news: dict[str, Any]) -> bool:
    text = _combined_text(news)
    return any(keyword in text for keyword in TECH_KEYWORDS)


def has_news_event_signal(news: dict[str, Any]) -> bool:
    text = _combined_text(news)
    return any(keyword in text for keyword in NEWS_EVENT_KEYWORDS)


def is_low_news_value_material(news: dict[str, Any]) -> bool:
    title = (news.get("title") or "").lower()
    return any(pattern in title for pattern in LOW_NEWS_VALUE_PATTERNS)


def is_political_news(news: dict[str, Any]) -> bool:
    text = _combined_text(news)

    for phrase in POLITICAL_STOP_PHRASES:
        if phrase.lower() in text:
            return True

    for word in POLITICAL_STOP_WORDS:
        pattern = r"(?<![\wа-яёäöüß])" + re.escape(word.lower()) + r"(?![\wа-яёäöüß])"
        if re.search(pattern, text, flags=re.IGNORECASE):
            return True

    return False


def contains_political_text(text: str) -> bool:
    news = {"title": text, "summary": "", "source_name": "", "url": ""}
    return is_political_news(news)
