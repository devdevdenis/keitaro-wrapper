"""CLI загрузки фикстур.

uv run python -m app.fixtures           # справочник стран
uv run python -m app.fixtures --demo    # + демо-кампании
uv run python -m app.fixtures --reset   # очистить таблицы перед загрузкой
"""

import argparse
import asyncio

from app.db import SessionLocal, engine
from app.fixtures import load_countries, load_demo_campaigns, reset


async def main(*, demo: bool, do_reset: bool) -> None:
    async with SessionLocal() as session:
        if do_reset:
            await reset(session)
            print("Таблицы очищены")
        print(f"Страны: {await load_countries(session)}")
        if demo:
            print(f"Демо-кампании: {await load_demo_campaigns(session)}")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Загрузка фикстур в БД")
    parser.add_argument("--demo", action="store_true", help="загрузить демо-кампании")
    parser.add_argument("--reset", action="store_true", help="очистить таблицы перед загрузкой")
    args = parser.parse_args()
    asyncio.run(main(demo=args.demo, do_reset=args.reset))
