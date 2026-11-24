"""Pytest-фикстуры: тестовая база Postgres, заглушка Keitaro и HTTP-клиент к API.

Тесты используют отдельную базу TEST_DATABASE_URL (по умолчанию keitaro_wrapper_test
на том же сервере, что и основная). Она создаётся автоматически; перед каждым тестом
схема пересоздаётся, так что тесты не зависят друг от друга.
"""

import asyncio
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_keitaro
from app.config import get_settings
from app.db import Base, get_session
from app.fixtures import load_countries
from app.main import app
from tests.fake_keitaro import FakeKeitaroClient

TEST_DATABASE_URL = make_url(get_settings().test_database_url)


async def _ensure_test_database() -> None:
    main_db = make_url(get_settings().database_url).database
    if TEST_DATABASE_URL.database == main_db:
        pytest.exit(f"TEST_DATABASE_URL указывает на основную базу «{main_db}» — тесты её сотрут")

    admin = create_async_engine(
        TEST_DATABASE_URL.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    try:
        async with admin.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": TEST_DATABASE_URL.database},
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{TEST_DATABASE_URL.database}"'))
    except OSError as exc:
        pytest.exit(
            f"Postgres недоступен ({TEST_DATABASE_URL.render_as_string(hide_password=True)}): "
            f"{exc}. Запустите `make db`."
        )
    finally:
        await admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def _test_database() -> None:
    asyncio.run(_ensure_test_database())


@pytest.fixture
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        await load_countries(session)  # фикстура справочника стран
    return factory


@pytest.fixture
async def session(session_factory) -> AsyncIterator[AsyncSession]:
    async with session_factory() as s:
        yield s


@pytest.fixture
def keitaro() -> FakeKeitaroClient:
    return FakeKeitaroClient()


@pytest.fixture
async def client(session_factory, keitaro) -> AsyncIterator[AsyncClient]:
    async def _session():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_keitaro] = lambda: keitaro
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def campaign_form() -> dict:
    return {
        "name": "campaign1",
        "country_codes": ["de"],
        "offer_id": 101,
        "domain_id": 1,
        "group_id": 1,
        "traffic_source_id": 1,
    }
