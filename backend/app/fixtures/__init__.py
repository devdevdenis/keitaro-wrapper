"""Фикстуры БД.

- countries.json      — справочник стран ISO 3166-1 (обязательная фикстура);
- demo_campaigns.json — демо-записи кампаний (для разработки, опционально).

Загрузка идемпотентна: повторный запуск обновляет записи, а не дублирует их.
"""

import json
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Campaign, Country

DATA_DIR = Path(__file__).parent / "data"


def read_fixture(name: str) -> list[dict]:
    return json.loads((DATA_DIR / f"{name}.json").read_text(encoding="utf-8"))


async def load_countries(session: AsyncSession) -> int:
    rows = read_fixture("countries")
    for row in rows:
        await session.merge(Country(**row))
    await session.commit()
    return len(rows)


async def load_demo_campaigns(session: AsyncSession) -> int:
    rows = read_fixture("demo_campaigns")
    for row in rows:
        existing = await session.scalar(
            select(Campaign).where(Campaign.keitaro_id == row["keitaro_id"])
        )
        if existing is None:
            session.add(Campaign(**row))
        else:
            for key, value in row.items():
                setattr(existing, key, value)
    await session.commit()
    return len(rows)


async def reset(session: AsyncSession) -> None:
    await session.execute(delete(Campaign))
    await session.execute(delete(Country))
    await session.commit()
