from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional, Sequence

ATEN_URL = "https://vadzim.by/aten/"
REMOTE_JOBS_URL = "https://t.me/remote_belarus"
HOUSING_URL = "https://t.me/minsk_housing"
PROGRAMMER_BOT_URL = "https://t.me/vadzim_by_programmer_bot"
PROMO_INTERVAL_START = date(2026, 7, 1)

@dataclass(frozen=True)
class PromoButton:
    text: str
    url: str


@dataclass(frozen=True)
class PromoPost:
    key: str
    text: str
    buttons: tuple[PromoButton, ...]


@dataclass(frozen=True)
class PromoCampaign:
    key: str
    text: str
    button_text: str
    url: str
    at: time
    weekdays: Optional[set[int]] = None
    interval_days: Optional[int] = None

    def is_due(self, current: datetime) -> bool:
        if self.weekdays is not None and current.weekday() not in self.weekdays:
            return False
        if self.interval_days is not None:
            days_since_start = (current.date() - PROMO_INTERVAL_START).days
            if days_since_start < 0 or days_since_start % self.interval_days != 0:
                return False
        start = datetime.combine(current.date(), self.at, tzinfo=current.tzinfo)
        return current >= start

    def build_post(self) -> PromoPost:
        return PromoPost(
            key=self.key,
            text=self.text,
            buttons=(PromoButton(self.button_text, self.url),),
        )


def build_campaigns() -> tuple[PromoCampaign, ...]:
    return (
        PromoCampaign(
            key="aten_tue",
            at=time(12, 0),
            weekdays={1},
            url=ATEN_URL,
            button_text="Открыть ATEN",
            text="""<b>ATEN / Атон</b>

ATEN — цифровое пространство для нормального общения: написал главное, получил ответ, вернулся к делу.
Доступна веб-версия и Windows-клиент.""",
        ),
        PromoCampaign(
            key="aten_fri",
            at=time(12, 0),
            weekdays={4},
            url=ATEN_URL,
            button_text="Попробовать ATEN",
            text="""<b>ATEN / Атон</b>

ATEN — цифровое пространство для нормального общения: написал главное, получил ответ, вернулся к делу.
Доступна веб-версия и Windows-клиент.""",
        ),
        PromoCampaign(
            key="remote_belarus_weekly",
            at=time(12, 0),
            weekdays={2},
            url=REMOTE_JOBS_URL,
            button_text="Удалённая работа в Беларуси",
            text="""<b>Удалённая работа в Беларуси</b>

Ищете удалённую работу в Беларуси?
В канале публикуются вакансии для IT, маркетинга, дизайна и digital-специалистов.""",
        ),
        PromoCampaign(
            key="minsk_housing_weekly",
            at=time(12, 0),
            weekdays={6},
            url=HOUSING_URL,
            button_text="Квартиры в Минске",
            text="""<b>Квартиры в Минске</b>

Аренда, покупка и полезная информация по квартирам в Минске — в отдельной группе.""",
        ),
        PromoCampaign(
            key="programmer_bot_every_2_days",
            at=time(15, 0),
            interval_days=2,
            url=PROGRAMMER_BOT_URL,
            button_text="Открыть бота",
            text="""<b>Помощник программиста</b>

Бот для тех, кто изучает программирование. Помогает писать код, объясняет термины простыми словами и помогает разобраться в HTML, CSS, JavaScript, Python и других темах.""",
        ),
    )


def due_promo_posts(
    *,
    current: datetime,
    posted_keys: set[str],
    force: bool = False,
) -> list[PromoPost]:
    due: list[PromoPost] = []
    campaigns = sorted(
        build_campaigns(),
        key=lambda campaign: (campaign.at.hour, campaign.at.minute),
        reverse=True,
    )
    for campaign in campaigns:
        if campaign.key in posted_keys and not force:
            continue
        if force or campaign.is_due(current):
            due.append(campaign.build_post())
    return due


def next_promo_hint(
    *,
    current: datetime,
    posted_keys: set[str],
) -> Optional[str]:
    candidates: list[datetime] = []
    campaigns: Sequence[PromoCampaign] = build_campaigns()
    for days_ahead in range(8):
        day = current.date() + timedelta(days=days_ahead)
        for campaign in campaigns:
            if days_ahead == 0 and campaign.key in posted_keys:
                continue
            target = datetime.combine(day, campaign.at, tzinfo=current.tzinfo)
            if target <= current:
                continue
            if campaign.weekdays is not None and target.weekday() not in campaign.weekdays:
                continue
            if campaign.interval_days is not None:
                days_since_start = (target.date() - PROMO_INTERVAL_START).days
                if days_since_start < 0 or days_since_start % campaign.interval_days != 0:
                    continue
            if campaign.weekdays is None and campaign.interval_days is None:
                continue
            candidates.append(target)

    if not candidates:
        return None
    return min(candidates).strftime("%d.%m %H:%M")
