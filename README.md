# Keitaro Wrapper

Обёртка над [Admin API](https://admin-api.docs.keitaro.io/) трекера Keitaro: быстрое создание
тестовых кампаний по шаблону и редактор офферов в потоках.

**Стек:** FastAPI · SQLAlchemy 2 (async) · Alembic · httpx — Vue 3 (Composition API) · Vite · Vue Router.

## Возможности

### 1. Создание кампании

Форма принимает **название**, **гео (код страны)** и **ID оффера**, а также **домен**, **группу** и
**источник трафика** (списки подтягиваются из Keitaro API). Обёртка создаёт кампанию с двумя потоками:

| # | Поток      | Тип Keitaro | Схема      | Что делает                                                  |
|---|------------|-------------|------------|-------------------------------------------------------------|
| 1 | Google     | `forced`    | `redirect` | Фильтр `country = <гео>` → HTTP-редирект на `google.com`    |
| 2 | Offer      | `regular`   | `landings` | Весь остальной трафик → выбранный оффер (100%)              |

- К названию автоматически добавляется префикс `test_volper_` (`campaign1` → `test_volper_campaign1`).
  Префикс задаётся в `CAMPAIGN_NAME_PREFIX`.
- Alias кампании генерируется случайно, ссылка: `https://<домен>/<alias>`.
- Если поток создать не удалось, кампания отправляется в архив, чтобы в трекере не оставалось «полуготовых» кампаний.
- Созданная кампания сохраняется в локальной БД (таблица `campaigns`).

### 2. Редактор кампании (шаблон)

Показывает потоки кампании (фильтры, редирект, офферы) и умеет **добавлять и удалять офферы** в
потоках со схемой `landings`. Сейчас доли трафика делятся поровну; конкретные правила будут позже.

## Быстрый старт (локально)

Нужны: Python 3.12+ и [uv](https://docs.astral.sh/uv/), Node.js 20+.

```bash
make install         # uv sync + npm install + backend/.env из примера
```

Пропишите доступ к трекеру в `backend/.env`:

```dotenv
KEITARO_URL=https://your-tracker.com     # без /admin_api/v1
KEITARO_API_KEY=...                      # Maintenance → Users → Admin API keys
```

> Нет доступа к трекеру? Поставьте `KEITARO_MOCK=true`: API будет работать с in-memory заглушкой,
> в которой уже есть домены, группы, источники, офферы и две демо-кампании.

```bash
make migrate         # создать таблицы (SQLite по умолчанию: backend/keitaro_wrapper.db)
make fixtures        # справочник стран; make fixtures-demo — ещё и демо-кампании
make backend         # API: http://localhost:8000, Swagger: http://localhost:8000/docs
make frontend        # в другом терминале, UI: http://localhost:5173
```

Без `make` — те же команды вручную:

```bash
cd backend
uv sync
cp .env.example .env
uv run alembic upgrade head
uv run python -m app.fixtures --demo
uv run uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev          # /api проксируется на http://localhost:8000 (см. vite.config.js)
```

## Запуск в Docker

```bash
cp backend/.env.example backend/.env    # и заполните KEITARO_* (или KEITARO_MOCK=true)
docker compose up --build
```

- UI — http://localhost:8080 (nginx отдаёт статику и проксирует `/api` в бэкенд)
- API — http://localhost:8000/docs
- БД — PostgreSQL 17. Миграции и фикстура стран применяются при старте контейнера.
  Демо-кампании: `docker compose exec backend python -m app.fixtures --demo`.

## Фикстуры БД

Лежат в `backend/app/fixtures/data/`:

| Файл                  | Таблица     | Описание                                                   |
|-----------------------|-------------|------------------------------------------------------------|
| `countries.json`      | `countries` | 249 стран ISO 3166-1 alpha-2, источник для выбора гео        |
| `demo_campaigns.json` | `campaigns` | 2 демо-кампании `test_volper_*` (совпадают с mock-трекером) |

```bash
uv run python -m app.fixtures            # только страны
uv run python -m app.fixtures --demo     # + демо-кампании
uv run python -m app.fixtures --reset    # очистить таблицы и загрузить заново
```

Загрузка идемпотентна: повторный запуск обновляет записи, а не дублирует их. В тестах те же
фикстуры подключаются через pytest-фикстуры из `backend/tests/conftest.py` (БД в памяти + заглушка Keitaro).

## Тесты и линтер

```bash
make test            # pytest
make lint            # ruff
```

## Настройки (`backend/.env`)

| Переменная               | По умолчанию                              | Описание                                   |
|--------------------------|-------------------------------------------|--------------------------------------------|
| `DATABASE_URL`           | `sqlite+aiosqlite:///./keitaro_wrapper.db`| Для Postgres: `postgresql+asyncpg://…`     |
| `KEITARO_URL`            | —                                         | Адрес трекера                              |
| `KEITARO_API_KEY`        | —                                         | Admin API key                              |
| `KEITARO_MOCK`           | `false`                                   | Работать с заглушкой вместо трекера        |
| `CAMPAIGN_NAME_PREFIX`   | `test_volper_`                            | Префикс названий кампаний                  |
| `GOOGLE_REDIRECT_URL`    | `https://www.google.com`                  | Куда уводит поток №1                       |
| `STREAM_REDIRECT_ACTION` | `http`                                    | Тип редиректа потока (`action_type`)       |
| `COUNTRY_FILTER_NAME`    | `country`                                 | Имя фильтра страны в Keitaro               |
| `CORS_ORIGINS`           | `["http://localhost:5173"]`               | Разрешённые origin для фронта              |

## API

| Метод    | Путь                                      | Описание                                   |
|----------|-------------------------------------------|--------------------------------------------|
| `GET`    | `/api/health`                             | Статус и режим подключения к Keitaro       |
| `GET`    | `/api/countries`                          | Справочник стран (из БД)                   |
| `GET`    | `/api/keitaro/domains`                    | Домены                                     |
| `GET`    | `/api/keitaro/groups`                     | Группы кампаний                            |
| `GET`    | `/api/keitaro/traffic-sources`            | Источники трафика                          |
| `GET`    | `/api/keitaro/offers`                     | Офферы                                     |
| `GET`    | `/api/campaigns?mine=true`                | Кампании (по умолчанию — только с префиксом)|
| `POST`   | `/api/campaigns`                          | Создать кампанию с двумя потоками          |
| `GET`    | `/api/campaigns/{id}`                     | Кампания + потоки                          |
| `POST`   | `/api/streams/{id}/offers`                | Добавить оффер в поток                     |
| `DELETE` | `/api/streams/{id}/offers/{offer_id}`     | Удалить оффер из потока                    |

Пример создания кампании:

```bash
curl -X POST http://localhost:8000/api/campaigns \
  -H 'Content-Type: application/json' \
  -d '{"name": "campaign1", "country_code": "DE", "offer_id": 101,
       "domain_id": 1, "group_id": 1, "traffic_source_id": 1}'
```

## Структура

```
backend/
  app/
    main.py              # FastAPI-приложение, обработчики ошибок Keitaro
    config.py            # настройки (pydantic-settings)
    db.py, models.py     # SQLAlchemy: countries, campaigns
    schemas.py           # Pydantic-схемы
    keitaro/
      client.py          # httpx-клиент Admin API v1
      payloads.py        # сборка тел запросов (кампания, потоки, доли офферов)
      fake.py            # in-memory заглушка (KEITARO_MOCK=true, тесты)
    services/campaigns.py# бизнес-логика создания и редактирования
    api/routes/          # эндпоинты
    fixtures/            # JSON-фикстуры и CLI загрузки
  alembic/               # миграции
  tests/                 # pytest
frontend/
  src/
    api/                 # fetch-клиент
    composables/         # useAsync, useDictionaries, useHealth, useToast
    components/          # SearchSelect, StreamCard, FlowPreview, …
    views/               # список, создание, редактор кампании
```
