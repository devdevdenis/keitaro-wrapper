from fastapi import APIRouter, status

from app.api.deps import KeitaroDep, SessionDep, SettingsDep
from app.schemas import (
    CampaignCreate,
    CampaignDetail,
    CampaignIn,
    CampaignPushOut,
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
    data: CampaignCreate, keitaro: KeitaroDep, session: SessionDep, settings: SettingsDep
):
    """Создать кампанию сразу с двумя потоками: страны → Google, остальное → оффер."""
    campaign = await service.create_campaign(
        data, keitaro=keitaro, session=session, settings=settings
    )
    return _summary(campaign, tracked=True, countries=data.country_codes)


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


@router.post("/campaigns/{campaign_id}/push", response_model=CampaignPushOut)
async def push_campaign(
    campaign_id: int, keitaro: KeitaroDep, session: SessionDep, settings: SettingsDep
):
    """Push to KT: публикует черновики всех потоков кампании одной пачкой.

    422 — какой-то черновик не готов, 409 — поток изменили в Keitaro; в обоих случаях ничего не
    публикуется. Если Keitaro ответил ошибкой посреди публикации — 200 с failed_stream_id и error.
    """
    result = await editor.push_campaign(session, keitaro, campaign_id, settings)
    return CampaignPushOut(
        published=result.published,
        failed_stream_id=result.failed.id if result.failed else None,
        error=result.error,
        streams=[editor.view(s) for s in await editor.campaign_streams(session, campaign_id)],
    )


@router.delete("/campaigns/{campaign_id}/drafts", response_model=list[StreamOut])
async def cancel_campaign(campaign_id: int, session: SessionDep):
    """Cancel: отбросить все неопубликованные изменения потоков кампании."""
    return [editor.view(s) for s in await editor.cancel_campaign(session, campaign_id)]
