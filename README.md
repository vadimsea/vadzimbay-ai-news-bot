# Вадимбай News Bot

MVP-проект для автоматического Telegram-канала о нейтральных технологических новостях: ИИ, нейросети, робототехника, гаджеты, автоматизация, веб-дизайн, тренды веб-дизайна, AI-маркетинг, IT-стартапы и будущее технологий.

Политика, войны, армия, полиция, регулирование, санкции и геополитика запрещены. Если новость смешивает технологии с политическим или военным контекстом, бот должен ее отклонить.

## Структура

- `main.py` — полный цикл: сбор, фильтры, ранжирование, адаптация, публикация.
- `config.py` — настройки из `.env`.
- `sources.py` — RSS-источники.
- `fetcher.py` — загрузка и нормализация RSS.
- `filters.py` — свежесть, релевантность, политический и военный стоп-фильтр.
- `blocked_sources.py` — обход источников из локального denylist.
- `ranker.py` — выбор лучшей новости.
- `translator.py` — адаптация на русский через OpenAI API или fallback-шаблон.
- `telegram_publisher.py` — публикация через Telegram Bot API.
- `storage.py` — JSON-хранилище опубликованных ссылок.
- `scheduler.py` — ежедневный запуск через APScheduler.

## 1. Создать Telegram-бота

1. Откройте Telegram и найдите `@BotFather`.
2. Отправьте `/newbot`.
3. Задайте имя и username бота.
4. BotFather выдаст `TELEGRAM_BOT_TOKEN`.

## 2. Добавить бота в канал

1. Откройте настройки канала.
2. Добавьте созданного бота в администраторы.
3. Дайте право публиковать сообщения.

## 3. Узнать `TELEGRAM_CHANNEL_ID`

Самый простой вариант для публичного канала: используйте `@username_канала`.

Для приватного канала можно временно отправить сообщение в канал и вызвать:

```bash
curl "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getUpdates"
```

В ответе найдите `chat.id`. Обычно он выглядит как `-1001234567890`.

## 4. Настроить `.env`

Скопируйте пример:

```bash
cp .env.example .env
```

Заполните:

```env
TELEGRAM_BOT_TOKEN=123456:token
TELEGRAM_CHANNEL_ID=@your_channel
OPENAI_API_KEY=
POST_TIME=10:00
MORNING_WINDOW=09:00-11:50
EVENING_WINDOW=17:00-20:30
TIMEZONE=Europe/Minsk
MAX_NEWS_AGE_HOURS=48
DRY_RUN=true
MODERATION_ENABLED=true
MODERATION_CHAT_ID=@vadzimbelarus
MODERATION_TIMEOUT_MINUTES=120
```

`DRY_RUN=true` означает, что бот ничего не публикует, а печатает выбранную новость и итоговый пост в консоль.

`MODERATION_ENABLED=true` означает, что перед публикацией бот отправит превью в `MODERATION_CHAT_ID` с кнопками подтверждения и отклонения.

## 5. Установить зависимости

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Для Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 6. Тестовый запуск без публикации

Убедитесь, что в `.env` стоит:

```env
DRY_RUN=true
```

Запустите:

```bash
python main.py --once
```

В консоли появятся:

- выбранная новость;
- причина выбора;
- итоговый текст поста;
- ссылка на первоисточник;
- `image_url`, если он найден.

## 7. Реальная публикация

Проверьте, что бот администратор канала, затем поставьте:

```env
DRY_RUN=false
```

Запустите:

```bash
python main.py --once
```

После успешной публикации ссылка будет записана в `published.json`, чтобы не публиковать ее повторно.

## 8. Ежедневный запуск как процесс

Можно держать процесс запущенным:

```bash
python main.py --schedule
```

При запуске через `--schedule` бот планирует две публикации в день в случайное время:

- `MORNING_WINDOW=09:00-11:50` — до обеда;
- `EVENING_WINDOW=17:00-20:30` — после 17:00;
- `TIMEZONE=Europe/Minsk` — часовой пояс Минска.

Каждый день после полуночи время публикаций пересчитывается заново.

## 9. Cron

Откройте crontab:

```bash
crontab -e
```

Пример запуска два раза в день через cron, если не используете встроенный scheduler. Точное случайное время в этом варианте лучше задавать средствами cron/systemd, поэтому для рандома предпочтительнее `python main.py --schedule`.

Пример фиксированного запуска:

```cron
0 10 * * * cd /path/to/project && /path/to/project/.venv/bin/python main.py --once >> bot.log 2>&1
15 18 * * * cd /path/to/project && /path/to/project/.venv/bin/python main.py --once >> bot.log 2>&1
```

## 10. systemd timer

Создайте `/etc/systemd/system/vadzimbay-news.service`:

```ini
[Unit]
Description=Vadzimbay daily tech news bot

[Service]
Type=oneshot
WorkingDirectory=/path/to/project
ExecStart=/path/to/project/.venv/bin/python /path/to/project/main.py --once
```

Создайте `/etc/systemd/system/vadzimbay-news.timer`:

```ini
[Unit]
Description=Run Vadzimbay news bot daily

[Timer]
OnCalendar=*-*-* 10:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Включите таймер:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now vadzimbay-news.timer
```

## 10.1. GitHub Actions

Если есть только FTP-хостинг, бот можно запускать через GitHub Actions. В проекте есть workflow:

```text
.github/workflows/vadzimbay-news.yml
```

Он запускается два раза в день:

- утром в окне `09:00-11:50` по Минску;
- вечером в окне `17:00-20:30` по Минску.

Внутри каждого окна workflow делает случайную задержку, затем запускает:

```bash
python main.py --once
```

После успешной публикации workflow коммитит `published.json`, чтобы не публиковать одну ссылку повторно.

В GitHub нужно добавить secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID`
- `OPENAI_API_KEY`
- `MODERATION_CHAT_ID`

Путь: `Settings` → `Secrets and variables` → `Actions` → `New repository secret`.

Можно также добавить variable:

- `OPENAI_MODEL`, например `gpt-4.1-mini`

## 11. OpenAI API

Без `OPENAI_API_KEY` используется простой fallback-шаблон. Для нормальной живой адаптации на русский добавьте ключ:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
```

LLM получает только заголовок, краткое описание, источник и ссылку. Полные статьи бот не копирует.

## 12. Добавление RSS-источников

Откройте `sources.py` и добавьте:

```python
NewsSource("Source Name", "https://example.com/feed.xml", "en", "ai", 0.8)
```

Поля:

- `name` — название источника;
- `url` — RSS URL;
- `language` — `en`, `de`, `ru`, `zh`, `he`;
- `category` — например `ai`, `robotics`, `technology`;
- `trust_score` — базовое доверие от `0.0` до `1.0`.

Китайские и ивритские источники можно добавить там же. `main.py` менять не нужно.

## 13. Расширение стоп-слов

Откройте `filters.py` и расширьте:

- `POLITICAL_STOP_WORDS`;
- `POLITICAL_STOP_PHRASES`.

Для канала действует строгий принцип: если есть сомнение, новость лучше отклонить.

## 14. Обход запрещенных источников

В Беларуси перечни материалов и ресурсов, признанных экстремистскими, меняются. Поэтому бот использует локальный denylist `blocked_sources.json`, который нужно поддерживать вручную по актуальному официальному списку.

Формат:

```json
{
  "domains": [
    "example-blocked-source.by"
  ],
  "source_names": [
    "Example Blocked Source"
  ],
  "keywords": [
    "example blocked brand"
  ]
}
```

Проверка применяется дважды:

- до загрузки RSS — источник полностью пропускается, если его домен или название есть в списке;
- перед ранжированием — отдельная новость отклоняется, если ее URL, источник или ключевые слова попали в denylist.

Если список обновился, достаточно изменить `blocked_sources.json`. Код менять не нужно.
