.PHONY: install migrate fixtures backend frontend test lint build up down

install:            ## установить зависимости бэка и фронта
	cd backend && uv sync
	cd frontend && npm install
	test -f backend/.env || cp backend/.env.example backend/.env

migrate:            ## применить миграции
	cd backend && uv run alembic upgrade head

fixtures:           ## загрузить справочник стран
	cd backend && uv run python -m app.fixtures

backend:            ## API на http://localhost:8000 (Swagger: /docs)
	cd backend && uv run uvicorn app.main:app --reload --port 8000

frontend:           ## UI на http://localhost:5173
	cd frontend && npm run dev

test:               ## тесты бэкенда
	cd backend && uv run pytest

lint:               ## линтер и форматирование
	cd backend && uv run ruff check . && uv run ruff format --check .

build:              ## сборка фронта
	cd frontend && npm run build

up:                 ## всё в Docker: http://localhost:8080
	docker compose up --build -d

down:
	docker compose down
