# uv ставится в ~/.local/bin (или ~/.cargo/bin), а эти папки часто не попадают в PATH
# терминалов IDE (например, Run из README в PhpStorm). Добавляем их явно.
export PATH := $(HOME)/.local/bin:$(HOME)/.cargo/bin:$(PATH)

.PHONY: install migrate fixtures fixtures-reset backend frontend test lint build up down check-uv

check-uv:
	@command -v uv >/dev/null 2>&1 || { \
		echo "uv не найден. Установите: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; }

install: check-uv   ## установить зависимости бэка и фронта
	cd backend && uv sync
	cd frontend && npm ci
	test -f backend/.env || cp backend/.env.example backend/.env

migrate: check-uv   ## применить миграции
	cd backend && uv run alembic upgrade head

fixtures: check-uv  ## загрузить справочник стран
	cd backend && uv run python -m app.fixtures

fixtures-reset: check-uv  ## очистить таблицы и загрузить справочник заново
	cd backend && uv run python -m app.fixtures --reset

backend: check-uv   ## API на http://localhost:8000 (Swagger: /docs)
	cd backend && uv run uvicorn app.main:app --reload --port 8000

frontend:           ## UI на http://localhost:5173
	cd frontend && npm run dev

test: check-uv      ## тесты бэкенда
	cd backend && uv run pytest

lint: check-uv      ## линтер и форматирование
	cd backend && uv run ruff check . && uv run ruff format --check .

build:              ## сборка фронта
	cd frontend && npm run build

up:                 ## всё в Docker: http://localhost:8080
	docker compose up --build -d

down:
	docker compose down
