"""Бизнес-логика: создание кампаний и редактирование офферов в потоках."""

import logging
from contextlib import suppress

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.keitaro import KeitaroAPI, KeitaroError
from app.keitaro import payloads as p
from app.keitaro.client import JSON
from app.models import Campaign, Country
from app.schemas import CampaignCreate

logger = logging.getLogger(__name__)


class ServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


async def create_campaign(
    data: CampaignCreate, *, keitaro: KeitaroAPI, session: AsyncSession, settings: Settings
) -> tuple[Campaign, list[JSON]]:
    """Создаёт кампанию в Keitaro с двумя потоками и сохраняет локальную запись.

    1. Кампания с доменом, группой и источником.
    2. Поток forced: страна == country_code → редирект на Google.
    3. Поток regular: остальной трафик → выбранный оффер.
    Если потоки создать не удалось — кампания отправляется в архив (откат).
    """
    if await session.get(Country, data.country_code) is None:
        raise ServiceError(f"Неизвестный код страны: {data.country_code}", status_code=422)

    campaign = await keitaro.create_campaign(
        p.campaign_payload(
            name=p.campaign_name(data.name, settings.campaign_name_prefix),
            alias=p.generate_alias(),
            domain_id=data.domain_id,
            group_id=data.group_id,
            traffic_source_id=data.traffic_source_id,
        )
    )
    campaign_id = int(campaign["id"])

    try:
        google_stream = await keitaro.create_stream(
            p.google_stream_payload(
                campaign_id=campaign_id, country_code=data.country_code, settings=settings
            )
        )
        offer_stream = await keitaro.create_stream(
            p.offer_stream_payload(
                campaign_id=campaign_id, offer_id=data.offer_id, settings=settings
            )
        )
    except KeitaroError:
        logger.warning("Не удалось создать потоки, архивируем кампанию %s", campaign_id)
        with suppress(KeitaroError):
            await keitaro.delete_campaign(campaign_id)
        raise

    record = Campaign(
        keitaro_id=campaign_id,
        alias=campaign["alias"],
        name=campaign["name"],
        country_code=data.country_code,
        offer_id=data.offer_id,
        domain_id=data.domain_id,
        group_id=data.group_id,
        traffic_source_id=data.traffic_source_id,
        google_stream_id=google_stream.get("id"),
        offer_stream_id=offer_stream.get("id"),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record, [google_stream, offer_stream]


async def get_record(session: AsyncSession, keitaro_id: int) -> Campaign | None:
    result = await session.execute(select(Campaign).where(Campaign.keitaro_id == keitaro_id))
    return result.scalar_one_or_none()


async def list_records(session: AsyncSession) -> dict[int, Campaign]:
    result = await session.execute(select(Campaign))
    return {c.keitaro_id: c for c in result.scalars()}


# --- редактор офферов (шаблон; правила уточнятся) ---------------------------


async def _offer_stream(keitaro: KeitaroAPI, stream_id: int) -> JSON:
    stream = await keitaro.get_stream(stream_id)
    if stream.get("schema") != "landings":
        raise ServiceError("Офферы можно менять только в потоке со схемой «landings»")
    return stream


async def add_offer(keitaro: KeitaroAPI, stream_id: int, offer_id: int) -> JSON:
    stream = await _offer_stream(keitaro, stream_id)
    offer_ids = [int(o["offer_id"]) for o in stream.get("offers", [])]
    if offer_id in offer_ids:
        raise ServiceError("Этот оффер уже есть в потоке", status_code=409)
    return await keitaro.update_stream(
        stream_id, {"offers": p.rebalance_offers([*offer_ids, offer_id])}
    )


async def remove_offer(keitaro: KeitaroAPI, stream_id: int, offer_id: int) -> JSON:
    stream = await _offer_stream(keitaro, stream_id)
    offer_ids = [int(o["offer_id"]) for o in stream.get("offers", [])]
    if offer_id not in offer_ids:
        raise ServiceError("Оффера нет в потоке", status_code=404)
    if len(offer_ids) == 1:
        raise ServiceError("Нельзя удалить последний оффер из потока", status_code=409)
    remaining = [o for o in offer_ids if o != offer_id]
    return await keitaro.update_stream(stream_id, {"offers": p.rebalance_offers(remaining)})
