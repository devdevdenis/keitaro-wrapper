"""Фикстуры БД: countries.json — справочник стран ISO 3166-1 alpha-2.

Загрузка идемпотентна: повторный запуск обновляет записи, а не дублирует их.
"""

import json
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Campaign, Country, StreamState

DATA_DIR = Path(__file__).parent / "data"


def read_fixture(name: str) -> list[dict]:
    return json.loads((DATA_DIR / f"{name}.json").read_text(encoding="utf-8"))


async def load_countries(session: AsyncSession) -> int:
    rows = read_fixture("countries")
    for row in rows:
        await session.merge(Country(**row))
    await session.commit()
    return len(rows)


async def reset(session: AsyncSession) -> None:
    await session.execute(delete(StreamState))
    await session.execute(delete(Campaign))
    await session.execute(delete(Country))
    await session.commit()
