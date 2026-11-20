# Keitaro Wrapper

Обёртка над [Admin API](https://admin-api.docs.keitaro.io/) трекера Keitaro: создание кампаний и редактор офферов в потоках.

**Стек:** FastAPI · SQLAlchemy 2 (async) · PostgreSQL · Alembic · httpx — Vue 3 (Composition API) · Vite · Vue Router.

## Возможности

Описание возможностей для пользователя — в [docs/](docs/README.md).

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

### 2. Редактор кампании

Показывает потоки кампании: потоки со схемой `landings` — таблицей «оффер — доля — действия»,
остальные — только названием. Правила для пользователя — в [docs/campaign-editor.md](docs/campaign-editor.md).

- **Add / Remove / Bring Back** и закрепление доли копятся в черновике в локальной БД (таблица
  `stream_states`); поток с черновиком подсвечивается, Keitaro не меняется.
- Доли пересчитываются сразу: удалённые — 0 %, закреплённые сохраняют долю, остаток делится
  поровну (лишние проценты — первым офферам). Закрепление долей не меняет, снятие — пересчитывает.
- **Push to KT** заменяет офферы потока в Keitaro (`PUT /streams/{id}`), **Cancel** отбрасывает
  черновик. Удалённые офферы остаются в списке со статусом Removed — их можно вернуть.
- Push недоступен, если удалены все офферы или освободившуюся долю некому отдать (все закреплены).
- При каждом открытии редактора офферы сверяются с Keitaro: удалённые там помечаются Removed,
  добавленные появляются, доли берутся из Keitaro. Если поток изменили в Keitaro, пока был черновик,
  публикация блокируется (409), чтобы не затереть чужие правки.

## Быстрый старт (локально)

Нужны: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 20+, Docker (для PostgreSQL).

> `make` сам ищет `uv` в `~/.local/bin` и `~/.cargo/bin`, поэтому команды работают и в терминале
> IDE (например, кнопка Run в README в PhpStorm). Чтобы вызывать `uv` напрямую, добавьте его в PATH:
> `echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc`.

Установить зависимости бэкенда и фронта и создать `backend/.env` из примера:

```bash
make install
```

Пропишите доступ к трекеру в `backend/.env` (адрес без `/admin_api/v1`, ключ —
Maintenance → Users → Admin API keys):

```dotenv
KEITARO_URL=https://your-tracker.com
KEITARO_API_KEY=...
```

Поднять PostgreSQL 17 (контейнер `db` из `docker-compose.yml`, `localhost:5432`, keitaro / keitaro):

```bash
make db
```

Создать таблицы:

```bash
make migrate
```

Загрузить справочник стран:

```bash
make fixtures
```

Запустить API — http://localhost:8000, Swagger — http://localhost:8000/docs:

```bash
make backend
```

В другом терминале запустить UI — http://localhost:5173 (`/api` проксируется на бэкенд,
см. `vite.config.js`):

```bash
make frontend
```

Без `make` — те же команды вручную:

```bash
docker compose up -d --wait db
```

```bash
cd backend
uv sync
cp .env.example .env
uv run alembic upgrade head
uv run python -m app.fixtures
uv run uvicorn app.main:app --reload
```

```bash
cd frontend
npm ci
npm run dev
```

## Запуск в Docker

Скопируйте пример настроек и заполните `KEITARO_URL` / `KEITARO_API_KEY`:

```bash
cp backend/.env.example backend/.env
```

```bash
docker compose up --build
```

- UI — http://localhost:8080 (nginx отдаёт статику и проксирует `/api` в бэкенд)
- API — http://localhost:8000/docs
- БД — PostgreSQL 17 на `localhost:5432` (keitaro / keitaro). Миграции и фикстура стран
  применяются при старте контейнера.

## Фикстуры БД

`backend/app/fixtures/data/countries.json` → таблица `countries`: 249 стран ISO 3166-1 alpha-2,
из них выбирается гео при создании кампании.

Загрузить справочник:

```bash
make fixtures
```

Очистить таблицы и загрузить заново:

```bash
make fixtures-reset
```

Загрузка идемпотентна: повторный запуск обновляет записи, а не дублирует их. В тестах справочник
подключается через pytest-фикстуры из `backend/tests/conftest.py`.

## Тесты и линтер

```bash
make test
```

```bash
make lint
```

Для тестов нужен запущенный PostgreSQL (`make db`). Они работают в отдельной базе
`keitaro_wrapper_test` (`TEST_DATABASE_URL`), которая создаётся автоматически; схема
пересоздаётся перед каждым тестом, основная база не затрагивается.

К настоящему трекеру тесты не обращаются: Keitaro подменяется заглушкой из
`backend/tests/fake_keitaro.py`.

## Настройки (`backend/.env`)

| Переменная               | По умолчанию                              | Описание                                   |
|--------------------------|-------------------------------------------|--------------------------------------------|
| `DATABASE_URL`           | `postgresql+asyncpg://keitaro:keitaro@localhost:5432/keitaro_wrapper` | Основная база |
| `TEST_DATABASE_URL`      | `postgresql+asyncpg://keitaro:keitaro@localhost:5432/keitaro_wrapper_test` | База для pytest |
| `KEITARO_URL`            | —                                         | Адрес трекера                              |
| `KEITARO_API_KEY`        | —                                         | Admin API key                              |
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
| `GET`    | `/api/campaigns/{id}`                     | Кампания + потоки; сверяет офферы с Keitaro |
| `POST`   | `/api/streams/{id}/offers`                | Черновик: добавить оффер (`{"offer_id"}`)  |
| `DELETE` | `/api/streams/{id}/offers/{offer_id}`     | Черновик: удалить оффер                    |
| `POST`   | `/api/streams/{id}/offers/{offer_id}/restore` | Черновик: вернуть удалённый оффер      |
| `PUT`    | `/api/streams/{id}/offers/{offer_id}/pin` | Черновик: закрепить долю (`{"pinned": true}`) или снять |
| `POST`   | `/api/streams/{id}/push`                  | Push to KT — опубликовать черновик         |
| `DELETE` | `/api/streams/{id}/draft`                 | Cancel — отбросить черновик                |

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
    db.py, models.py     # SQLAlchemy: countries, campaigns, stream_states
    schemas.py           # Pydantic-схемы
    keitaro/
      client.py          # httpx-клиент Admin API v1
      payloads.py        # сборка тел запросов (кампания, потоки, офферы потока)
    services/
      campaigns.py       # создание кампании
      offer_shares.py    # правила редактора: пересчёт долей, сверка с Keitaro
      stream_editor.py   # черновики потоков, Push to KT, Cancel
    api/routes/          # эндпоинты
    fixtures/            # JSON-фикстуры и CLI загрузки
  alembic/               # миграции
  tests/                 # pytest + заглушка Keitaro для тестов
frontend/
  src/
    api/                 # fetch-клиент
    composables/         # useAsync, useDictionaries, useHealth, useToast
    components/          # SearchSelect, OfferStreamCard, FlowPreview, …
    views/               # список, создание, редактор кампании
```
