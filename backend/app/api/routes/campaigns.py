from fastapi import APIRouter, Query, status

from app.api.deps import KeitaroDep, SessionDep, SettingsDep
from app.schemas import (
    CampaignCreate,
    CampaignCreated,
    CampaignDetail,
    CampaignRecord,
    CampaignSummary,
    StreamOfferAdd,
    StreamOut,
)
from app.services import campaigns as service

router = APIRouter(tags=["campaigns"])


def _summary(campaign: dict, record) -> dict:
    data = dict(campaign)
    if record is not None:
        data.update(tracked=True, country_code=record.country_code, domain_id=record.domain_id)
    return data


@router.get("/campaigns", response_model=list[CampaignSummary])
async def list_campaigns(
    keitaro: KeitaroDep,
    session: SessionDep,
    settings: SettingsDep,
    mine: bool = Query(True, description="Только кампании с префиксом CAMPAIGN_NAME_PREFIX"),
):
    records = await service.list_records(session)
    campaigns = await keitaro.list_campaigns()
    if mine:
        campaigns = [c for c in campaigns if c["name"].startswith(settings.campaign_name_prefix)]
    campaigns.sort(key=lambda c: c["id"], reverse=True)
    return [_summary(c, records.get(c["id"])) for c in campaigns]


@router.post("/campaigns", response_model=CampaignCreated, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    data: CampaignCreate, keitaro: KeitaroDep, session: SessionDep, settings: SettingsDep
):
    record, streams = await service.create_campaign(
        data, keitaro=keitaro, session=session, settings=settings
    )
    return CampaignCreated(
        record=CampaignRecord.model_validate(record),
        streams=[StreamOut.model_validate(s) for s in streams],
    )


@router.get("/campaigns/{campaign_id}", response_model=CampaignDetail)
async def get_campaign(campaign_id: int, keitaro: KeitaroDep, session: SessionDep):
    campaign = await keitaro.get_campaign(campaign_id)
    streams = await keitaro.list_streams(campaign_id)
    record = await service.get_record(session, campaign_id)
    return {
        **_summary(campaign, record),
        "streams": streams,
        "record": CampaignRecord.model_validate(record) if record else None,
    }


# --- редактор офферов в потоке (шаблон) --------------------------------------


@router.post("/streams/{stream_id}/offers", response_model=StreamOut)
async def add_offer_to_stream(stream_id: int, data: StreamOfferAdd, keitaro: KeitaroDep):
    return await service.add_offer(keitaro, stream_id, data.offer_id)


@router.delete("/streams/{stream_id}/offers/{offer_id}", response_model=StreamOut)
async def remove_offer_from_stream(stream_id: int, offer_id: int, keitaro: KeitaroDep):
    return await service.remove_offer(keitaro, stream_id, offer_id)
