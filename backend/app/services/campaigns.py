"""Кампании: создание, правка параметров, удаление. Потоки — services/stream_editor.py."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.keitaro import KeitaroAPI
from app.keitaro import payloads as p
from app.keitaro.client import JSON
from app.models import Campaign, StreamState
from app.schemas import CampaignIn
from app.services import stream_editor


async def create_campaign(
    data: CampaignIn, *, keitaro: KeitaroAPI, session: AsyncSession, settings: Settings
) -> JSON:
    """Создаёт кампанию в Keitaro — без потоков — и сохраняет локальную запись.

    Потоки появляются в редакторе как шаблоны (Flow 1 — перехватывающий, Flow 2 — обычный) и
    попадают в Keitaro, только когда их опубликуют.
    """
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
    await stream_editor.add_templates(session, campaign_id, settings)
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
