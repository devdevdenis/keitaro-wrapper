"""Бизнес-логика создания кампаний. Редактор офферов — services/stream_editor.py."""

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
from app.services.errors import ServiceError
from app.services.offers import ensure_offer_available

logger = logging.getLogger(__name__)


async def create_campaign(
    data: CampaignCreate, *, keitaro: KeitaroAPI, session: AsyncSession, settings: Settings
) -> tuple[Campaign, list[JSON]]:
    """Создаёт кампанию в Keitaro с двумя потоками и сохраняет локальную запись.

    0. Проверка оффера — до создания кампании, чтобы не создавать и не откатывать её.
    1. Кампания с доменом, группой и источником.
    2. Поток forced: страна ∈ country_codes → редирект на Google.
    3. Поток regular: остальной трафик → выбранный оффер.
    Если потоки создать не удалось — кампания отправляется в архив (откат).
    """
    await _ensure_countries_known(session, data.country_codes)
    await ensure_offer_available(keitaro, data.offer_id)

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
                campaign_id=campaign_id, country_codes=data.country_codes, settings=settings
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
        country_codes=data.country_codes,
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


async def _ensure_countries_known(session: AsyncSession, codes: list[str]) -> None:
    known = set(await session.scalars(select(Country.code).where(Country.code.in_(codes))))
    unknown = [code for code in codes if code not in known]
    if len(unknown) == 1:
        raise ServiceError(f"Неизвестный код страны: {unknown[0]}", status_code=422)
    if unknown:
        raise ServiceError(f"Неизвестные коды стран: {', '.join(unknown)}", status_code=422)


async def get_record(session: AsyncSession, keitaro_id: int) -> Campaign | None:
    result = await session.execute(select(Campaign).where(Campaign.keitaro_id == keitaro_id))
    return result.scalar_one_or_none()


async def list_records(session: AsyncSession) -> dict[int, Campaign]:
    result = await session.execute(select(Campaign))
    return {c.keitaro_id: c for c in result.scalars()}
