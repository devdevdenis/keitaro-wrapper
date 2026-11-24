# Keitaro Wrapper

Интерфейс для трекера Keitaro поверх его [Admin API](https://admin-api.docs.keitaro.io/): список,
создание и правка кампаний, редактор потоков с черновиками и публикацией в Keitaro.

**Стек:** FastAPI · SQLAlchemy 2 (async) · PostgreSQL · Alembic · httpx — Vue 3 (Composition API) · Vite · Vue Router.

## Возможности

Описание для пользователя — в [docs/](docs/README.md). Ниже — как это устроено.

### 1. Список кампаний

Все кампании трекера (`GET /campaigns`), новые сверху. Поиск и пагинация — на клиенте: Keitaro не
отдаёт общее количество. Страница, размер страницы и поиск хранятся в query-параметрах `page`,
`per_page`, `q`; выбранный размер страницы ещё и в `localStorage`. Гео в списке — страны
опубликованных перехватывающих потоков из `stream_states`; `tracked` — кампания создана здесь
(есть запись в `campaigns`).

Удаление — `DELETE /campaigns/{id}` в Keitaro, то есть перенос в архив; локальная запись и потоки
редактора этой кампании удаляются.

### 2. Создание и параметры кампании

Страница кампании одна для создания и правки, в три колонки: параметры, потоки, схема потоков (уже
1600px схема уходит под параметры, уже 1080px — всё в одну колонку).

Форма принимает **название**, **домен**, **группу** и **источник трафика** (списки — из Keitaro API).
Кампания создаётся в Keitaro без потоков (`POST /campaigns`, `type=position`, alias случайный,
ссылка `https://<домен>/<alias>`), запись сохраняется в таблице `campaigns`. Название уходит в
Keitaro как есть (обрезаются только пробелы по краям). Сразу после создания у кампании два шаблона
потоков — черновики, которых в Keitaro ещё нет:

| Поток  | Тип Keitaro | Схема      | Шаблон                                                       |
|--------|-------------|------------|--------------------------------------------------------------|
| Flow 1 | `forced`    | `redirect` | Редирект на `GOOGLE_REDIRECT_URL`, страны не выбраны, `filter_or=true` (ИЛИ) |
| Flow 2 | `regular`   | `landings` | Без офферов                                                  |

Параметры существующей кампании сохраняются сразу (`PUT /campaigns/{id}`).

### 3. Редактор потоков

Правила для пользователя — в [docs/campaign-editor.md](docs/campaign-editor.md). Каждый поток
кампании — строка в `stream_states` (`keitaro_id = NULL` у ещё не опубликованного потока):
`saved` — поток, сверенный с Keitaro, `draft` — неопубликованные правки, `draft_base` — что было в
Keitaro, когда начали правку.

- **Перехватывающий** (`forced` + `redirect`): название, страны (фильтр `COUNTRY_FILTER_NAME`,
  `mode=accept`), логика фильтров `filter_or` (ИЛИ по умолчанию / И), адрес редиректа. Остальные
  фильтры потока при публикации сохраняются.
- **Обычный** (`landings`): название и офферы. **Add / Remove / Bring Back** и закрепление доли;
  доли пересчитываются сразу: удалённые — 0 %, закреплённые сохраняют долю, остаток делится
  поровну (лишние проценты — первым офферам). Закрепление долей не меняет, снятие — пересчитывает.
  Новый оффер проверяется в Keitaro (`GET /offers/{id}`): не найден или в архиве — 422.
- **Остальные** потоки показываются только названием; их можно удалить.
- Новый поток (`POST /api/campaigns/{id}/streams`) — шаблон обычного потока с названием Flow N.
  Пока поток не опубликован, его тип меняется (`PATCH` с `kind`): черновик заменяется шаблоном
  нового типа с тем же названием.
- Все правки копятся в черновике; **Push to KT** создаёт поток (`POST /streams`) или обновляет его
  (`PUT /streams/{id}`), **Cancel** отбрасывает черновик. Удаление потока — `DELETE /streams/{id}`
  (шаблон удаляется только у нас).
- Push недоступен, пока черновик не готов: нет названия, стран, корректного редиректа, офферов,
  удалены все офферы или освободившуюся долю некому отдать.
- При каждом открытии редактора потоки сверяются с Keitaro; удалённые там офферы помечаются
  Removed, удалённые потоки пропадают. Если поток изменили в Keitaro, пока был черновик,
  публикация блокируется (409), чтобы не затереть чужие правки.
- **Схема** на странице кампании показывает потоки в порядке проверки Keitaro (`forced` →
  `regular` → `default`, внутри — по позиции) с учётом черновиков.

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

`backend/app/fixtures/data/countries.json` → таблица `countries`: 249 стран ISO 3166-1 alpha-2.
Из них выбираются страны перехватывающего потока; коды проверяются по этой таблице.

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
| `KEITARO_TIMEOUT`        | `15`                                      | Таймаут запросов к Keitaro, секунд         |
| `GOOGLE_REDIRECT_URL`    | `https://www.google.com`                  | Редирект в шаблоне перехватывающего потока |
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
| `GET`    | `/api/campaigns`                          | Все кампании трекера; `tracked` — созданные здесь, а не в Keitaro |
| `POST`   | `/api/campaigns`                          | Создать кампанию без потоков (в редакторе — два шаблона) |
| `GET`    | `/api/campaigns/{id}`                     | Кампания + потоки; сверяет потоки с Keitaro |
| `PUT`    | `/api/campaigns/{id}`                     | Сохранить параметры кампании (сразу в Keitaro) |
| `DELETE` | `/api/campaigns/{id}`                     | Удалить кампанию (в Keitaro — в архив)     |
| `POST`   | `/api/campaigns/{id}/streams`             | Новый поток Flow N (тело необязательно: `{"kind": "intercept" \| "regular"}`, по умолчанию `regular`) |
| `PATCH`  | `/api/streams/{id}`                       | Черновик: название, тип (`kind`, только у неопубликованного), страны, `filter_or`, редирект |
| `DELETE` | `/api/streams/{id}`                       | Удалить поток (и в Keitaro, если опубликован) |
| `POST`   | `/api/streams/{id}/offers`                | Черновик: добавить оффер (`{"offer_id"}`)  |
| `DELETE` | `/api/streams/{id}/offers/{offer_id}`     | Черновик: удалить оффер                    |
| `POST`   | `/api/streams/{id}/offers/{offer_id}/restore` | Черновик: вернуть удалённый оффер      |
| `PUT`    | `/api/streams/{id}/offers/{offer_id}/pin` | Черновик: закрепить долю (`{"pinned": true}`) или снять |
| `POST`   | `/api/streams/{id}/push`                  | Push to KT — опубликовать черновик         |
| `DELETE` | `/api/streams/{id}/draft`                 | Cancel — отбросить черновик                |

`{id}` у `/api/streams/…` — id потока в нашей БД (поле `id` в ответе), а не в Keitaro: у
неопубликованного потока id в Keitaro ещё нет (`keitaro_id = null`).

Пример создания кампании:

```bash
curl -X POST http://localhost:8000/api/campaigns \
  -H 'Content-Type: application/json' \
  -d '{"name": "Nutra DE — Facebook", "domain_id": 1, "group_id": 1, "traffic_source_id": 1}'
```

## Структура

```
backend/
  app/
    main.py              # FastAPI-приложение, обработчики ошибок Keitaro
    config.py            # настройки (pydantic-settings)
    db.py, models.py     # SQLAlchemy: countries, campaigns, stream_states (потоки редактора)
    schemas.py           # Pydantic-схемы
    keitaro/
      client.py          # httpx-клиент Admin API v1
      payloads.py        # сборка тел запросов: кампания, офферы потока
    services/
      campaigns.py       # создание, правка и удаление кампании
      stream_editor.py   # потоки: сверка с Keitaro, шаблоны, черновики, Push to KT, Cancel, удаление
      stream_spec.py     # поток в редакторе: виды, шаблоны, проверка, тело запроса в Keitaro
      offer_shares.py    # офферы потока: пересчёт долей, сверка с Keitaro
      offers.py          # проверка оффера в Keitaro
      errors.py          # ServiceError → {"detail": …}
    api/routes/          # эндпоинты: campaigns, streams, dictionaries, meta
    fixtures/            # JSON-фикстуры и CLI загрузки
  alembic/               # миграции
  tests/                 # pytest + заглушка Keitaro для тестов
frontend/
  src/
    api/                 # fetch-клиент
    composables/         # useAsync, useDictionaries, useDeleteCampaign, useHealth, useToast
    components/          # StreamCard, InterceptFields, OfferTable, StreamsOverview,
                         # SearchSelect, TablePagination, ConfirmDialog, …
    views/
      CampaignsView.vue  # список кампаний
      CampaignView.vue   # страница кампании: создание, параметры, схема, потоки
```
