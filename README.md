# Keitaro Wrapper

Интерфейс для трекера Keitaro поверх его [Admin API](https://admin-api.docs.keitaro.io/): список
кампаний, создание кампании с потоками и редактор потоков с публикацией в Keitaro.

Описание для пользователя — в [docs/](docs/README.md).

**Стек:** FastAPI · SQLAlchemy 2 (async) · PostgreSQL · Alembic — Vue 3 · Vite.

## Запуск

Нужны Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 20+ и Docker.

1. Установить зависимости и создать `backend/.env`:

   ```bash
   make install
   ```

2. Указать в `backend/.env` адрес трекера и ключ Admin API (Maintenance → Users → Admin API keys):

   ```dotenv
   KEITARO_URL=https://your-tracker.com
   KEITARO_API_KEY=...
   ```

3. Поднять PostgreSQL и применить миграции:

   ```bash
   make db migrate
   ```

4. *(Опционально)* Загрузить справочник стран — без него при создании кампании не из чего
   выбрать гео:

   ```bash
   make fixtures
   ```

5. Запустить API (http://localhost:8000, Swagger — `/docs`):

   ```bash
   make backend
   ```

6. В другом терминале запустить UI (http://localhost:5173):

   ```bash
   make frontend
   ```

### Всё в Docker

Создать `backend/.env`, заполнить его, как в шаге 2, и запустить:

```bash
cp backend/.env.example backend/.env
```

```bash
docker compose up --build
```

UI — http://localhost:8080, API — http://localhost:8000/docs. Миграции и справочник стран
применяются при старте.

## Тесты

Нужен запущенный PostgreSQL (`make db`). Тесты работают в отдельной базе и к настоящему трекеру не
обращаются.

```bash
make test
```

```bash
make lint
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
      stream_editor.py   # потоки: сверка с Keitaro, черновики, Push to KT, Cancel, удаление
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
    components/          # StreamCard, OfferTable, StreamsOverview,
                         # SearchSelect, TablePagination, ConfirmDialog, …
    views/
      CampaignsView.vue  # список кампаний
      CampaignView.vue   # страница кампании: создание, параметры, схема, потоки
```
