from fastapi import APIRouter, status

from app.api.deps import KeitaroDep, SessionDep, SettingsDep
from app.schemas import (
    CampaignDetail,
    CampaignIn,
    CampaignRecord,
    CampaignSummary,
    StreamCreate,
    StreamOut,
)
from app.services import campaigns as service
from app.services import stream_editor as editor

router = APIRouter(tags=["campaigns"])


def _summary(campaign: dict, *, tracked: bool, countries: list[str]) -> dict:
    return {**campaign, "tracked": tracked, "country_codes": countries}


@router.get("/campaigns", response_model=list[CampaignSummary])
async def list_campaigns(keitaro: KeitaroDep, session: SessionDep):
    records = await service.list_records(session)
    countries = await editor.published_countries(session)
    campaigns = await keitaro.list_campaigns()
    campaigns.sort(key=lambda c: c["id"], reverse=True)
    return [
        _summary(c, tracked=c["id"] in records, countries=countries.get(c["id"], []))
        for c in campaigns
    ]


@router.post("/campaigns", response_model=CampaignSummary, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    data: CampaignIn, keitaro: KeitaroDep, session: SessionDep, settings: SettingsDep
):
    """Создать кампанию без потоков; в редакторе у неё появятся два шаблона потоков."""
    campaign = await service.create_campaign(
        data, keitaro=keitaro, session=session, settings=settings
    )
    return _summary(campaign, tracked=True, countries=[])


@router.get("/campaigns/{campaign_id}", response_model=CampaignDetail)
async def get_campaign(
    campaign_id: int, keitaro: KeitaroDep, session: SessionDep, settings: SettingsDep
):
    campaign = await keitaro.get_campaign(campaign_id)
    streams = await keitaro.list_streams(campaign_id)
    record = await service.get_record(session, campaign_id)
    # открытие редактора: подтягиваем изменения потоков, сделанные в Keitaro
    states = await editor.sync_campaign(session, campaign_id, streams, settings)
    return {
        **_summary(campaign, tracked=record is not None, countries=editor.published_in(states)),
        "streams": [editor.view(s) for s in states],
        "record": CampaignRecord.model_validate(record) if record else None,
    }


@router.put("/campaigns/{campaign_id}", response_model=CampaignSummary)
async def update_campaign(
    campaign_id: int, data: CampaignIn, keitaro: KeitaroDep, session: SessionDep
):
    """Сохранить параметры кампании — сразу в Keitaro."""
    campaign = await service.update_campaign(campaign_id, data, keitaro=keitaro, session=session)
    record = await service.get_record(session, campaign_id)
    countries = editor.published_in(await editor.campaign_streams(session, campaign_id))
    return _summary(campaign, tracked=record is not None, countries=countries)


@router.delete("/campaigns/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(campaign_id: int, keitaro: KeitaroDep, session: SessionDep) -> None:
    """Удалить кампанию — в Keitaro она перемещается в архив."""
    await service.delete_campaign(session, keitaro, campaign_id)


@router.post(
    "/campaigns/{campaign_id}/streams",
    response_model=StreamOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_stream(
    campaign_id: int,
    keitaro: KeitaroDep,
    session: SessionDep,
    settings: SettingsDep,
    data: StreamCreate | None = None,
):
    """Новый поток Flow N (по умолчанию обычный) — шаблон в черновике, в Keitaro — по Push to KT."""
    await keitaro.get_campaign(campaign_id)  # 404, если кампании нет
    kind = data.kind if data is not None else "regular"
    state = await editor.add_stream(session, campaign_id, kind, settings)
    return editor.view(state)
