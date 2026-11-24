"""Кампании: создание (сразу с двумя потоками), правка параметров, удаление."""

import logging
from contextlib import suppress
from dataclasses import replace

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.keitaro import KeitaroAPI, KeitaroError
from app.keitaro import payloads as p
from app.keitaro.client import JSON
from app.models import Campaign, StreamState
from app.schemas import CampaignCreate, CampaignIn
from app.services import stream_editor
from app.services import stream_spec as specs
from app.services.offer_shares import Offer
from app.services.offers import ensure_offer_available

logger = logging.getLogger(__name__)


async def create_campaign(
    data: CampaignCreate, *, keitaro: KeitaroAPI, session: AsyncSession, settings: Settings
) -> JSON:
    """Создаёт кампанию в Keitaro сразу с двумя потоками (по ТЗ) и сохраняет локальную запись.

    0. Проверки до создания — чтобы не создавать и не откатывать кампанию: страны есть в
       справочнике, оффер есть в Keitaro и не в архиве.
    1. Кампания с доменом, группой и источником.
    2. Flow 1 — перехватывающий: страна из списка → редирект на GOOGLE_REDIRECT_URL.
    3. Flow 2 — обычный: весь остальной трафик → выбранный оффер (100 %).
    Если поток создать не удалось — кампания отправляется в архив (откат).
    Дальше потоки правятся в редакторе как обычно.
    """
    await stream_editor.ensure_countries_known(session, data.country_codes)
    await ensure_offer_available(keitaro, data.offer_id)

    campaign = await keitaro.create_campaign(
        p.campaign_payload(
            name=data.name,
            alias=p.generate_alias(),
            domain_id=data.domain_id,
            group_id=data.group_id,
            traffic_source_id=data.traffic_source_id,
        )
    )
    campaign_id = int(campaign["id"])

    intercept = replace(
        specs.template("intercept", "Flow 1", settings), countries=tuple(data.country_codes)
    )
    regular = specs.template("regular", "Flow 2", settings).with_offers([Offer(data.offer_id, 100)])
    streams = []
    try:
        for position, spec in enumerate([intercept, regular], start=1):
            payload = specs.to_keitaro(spec, None, settings)
            streams.append(
                await keitaro.create_stream(
                    {**payload, "campaign_id": campaign_id, "position": position}
                )
            )
    except KeitaroError:
        logger.warning("Не удалось создать потоки, архивируем кампанию %s", campaign_id)
        with suppress(KeitaroError):
            await keitaro.delete_campaign(campaign_id)
        raise

    session.add(
        Campaign(
            keitaro_id=campaign_id,
            alias=campaign["alias"],
            name=campaign["name"],
            domain_id=data.domain_id,
            group_id=data.group_id,
            traffic_source_id=data.traffic_source_id,
        )
    )
    await session.commit()
    # потоки сразу появляются в редакторе (и гео — в списке кампаний)
    await stream_editor.sync_campaign(session, campaign_id, streams, settings)
    return campaign


async def update_campaign(
    campaign_id: int, data: CampaignIn, *, keitaro: KeitaroAPI, session: AsyncSession
) -> JSON:
    """Сохраняет параметры кампании сразу в Keitaro (PUT /campaigns/{id})."""
    campaign = await keitaro.update_campaign(campaign_id, data.model_dump())
    record = await get_record(session, campaign_id)
    if record is not None:
        for key, value in data.model_dump().items():
            setattr(record, key, value)
        await session.commit()
    if not campaign or "id" not in campaign:
        campaign = await keitaro.get_campaign(campaign_id)
    return campaign


async def delete_campaign(session: AsyncSession, keitaro: KeitaroAPI, campaign_id: int) -> None:
    """Удаляет кампанию: в Keitaro она уходит в архив (DELETE /campaigns/{id}).

    Вместе с ней стираются локальная запись и потоки редактора (черновики и шаблоны).
    """
    await keitaro.delete_campaign(campaign_id)  # 404, если кампании нет
    await session.execute(delete(Campaign).where(Campaign.keitaro_id == campaign_id))
    await session.execute(delete(StreamState).where(StreamState.campaign_id == campaign_id))
    await session.commit()


async def get_record(session: AsyncSession, keitaro_id: int) -> Campaign | None:
    result = await session.execute(select(Campaign).where(Campaign.keitaro_id == keitaro_id))
    return result.scalar_one_or_none()


async def list_records(session: AsyncSession) -> dict[int, Campaign]:
    result = await session.execute(select(Campaign))
    return {c.keitaro_id: c for c in result.scalars()}
