"""Справочники: страны (локальная БД) и сущности Keitaro для форм."""

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import KeitaroDep, SessionDep
from app.models import Country
from app.schemas import CountryOut, KeitaroEntity, OfferOut

router = APIRouter(tags=["dictionaries"])


@router.get("/countries", response_model=list[CountryOut])
async def list_countries(session: SessionDep):
    result = await session.execute(select(Country).order_by(Country.name))
    return result.scalars().all()


@router.get("/keitaro/domains", response_model=list[KeitaroEntity])
async def list_domains(keitaro: KeitaroDep):
    return [d for d in await keitaro.list_domains() if d.get("state") != "deleted"]


@router.get("/keitaro/groups", response_model=list[KeitaroEntity])
async def list_campaign_groups(keitaro: KeitaroDep):
    return await keitaro.list_groups("campaigns")


@router.get("/keitaro/traffic-sources", response_model=list[KeitaroEntity])
async def list_traffic_sources(keitaro: KeitaroDep):
    return [s for s in await keitaro.list_traffic_sources() if s.get("state") != "deleted"]


@router.get("/keitaro/offers", response_model=list[OfferOut])
async def list_offers(keitaro: KeitaroDep):
    return [o for o in await keitaro.list_offers() if o.get("state") != "deleted"]
