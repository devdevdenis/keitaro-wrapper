"""Pytest-фикстуры: изолированная БД в памяти, заглушка Keitaro и HTTP-клиент к API."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_keitaro
from app.db import Base, get_session
from app.fixtures import load_countries
from app.main import app
from tests.fake_keitaro import FakeKeitaroClient


@pytest.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
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
        "country_code": "de",
        "offer_id": 101,
        "domain_id": 1,
        "group_id": 1,
        "traffic_source_id": 1,
    }
