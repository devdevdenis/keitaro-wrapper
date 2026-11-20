from sqlalchemy import select

from app.keitaro.payloads import google_stream_name
from app.models import Campaign, StreamState


async def test_create_campaign_builds_two_streams(client, keitaro, campaign_form, session):
    response = await client.post("/api/campaigns", json=campaign_form)
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["record"]["name"] == "campaign1"
    assert body["record"]["country_codes"] == ["DE"]

    campaign = keitaro.campaigns[body["record"]["keitaro_id"]]
    assert campaign["domain_id"] == 1
    assert campaign["group_id"] == 1
    assert campaign["traffic_source_id"] == 1

    google, offer = body["streams"]
    assert google["type"] == "forced"
    assert google["schema"] == "redirect"
    assert google["action_payload"].startswith("https://www.google.com")
    assert google["filters"][0]["name"] == "country"
    assert google["filters"][0]["mode"] == "accept"
    assert google["filters"][0]["payload"] == ["DE"]

    assert offer["type"] == "regular"
    assert offer["schema"] == "landings"
    assert [(o["offer_id"], o["share"]) for o in offer["offers"]] == [(101, 100)]

    assert await session.get(Campaign, body["record"]["id"]) is not None


async def test_name_is_taken_as_is(client, keitaro, campaign_form):
    response = await client.post("/api/campaigns", json={**campaign_form, "name": "  Nutra DE  "})
    assert response.status_code == 201, response.text
    assert response.json()["record"]["name"] == "Nutra DE"  # только обрезаны пробелы
    assert keitaro.campaigns[response.json()["record"]["keitaro_id"]]["name"] == "Nutra DE"


async def test_several_countries_go_to_google(client, keitaro, campaign_form):
    form = {**campaign_form, "country_codes": ["de", " AT", "ch", "DE"]}
    response = await client.post("/api/campaigns", json=form)
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["record"]["country_codes"] == ["DE", "AT", "CH"]  # верхний регистр, без дублей
    google = body["streams"][0]
    assert google["name"] == "Google · DE, AT, CH"
    assert google["filters"][0]["payload"] == ["DE", "AT", "CH"]

    listed = (await client.get("/api/campaigns")).json()
    assert listed[0]["country_codes"] == ["DE", "AT", "CH"]


async def test_unknown_country_rejected(client, keitaro, campaign_form):
    response = await client.post(
        "/api/campaigns", json={**campaign_form, "country_codes": ["DE", "ZZ"]}
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Неизвестный код страны: ZZ"
    assert keitaro.campaigns == {}


async def test_country_list_is_required(client, campaign_form):
    for codes in ([], ["DEU"], None):
        response = await client.post(
            "/api/campaigns", json={**campaign_form, "country_codes": codes}
        )
        assert response.status_code == 422, codes


def test_google_stream_name_is_shortened():
    assert google_stream_name(["DE"]) == "Google · DE"
    codes = ["DE", "AT", "CH", "FR", "IT", "ES", "PT", "NL"]
    assert google_stream_name(codes) == "Google · DE, AT, CH, FR, IT +3"


async def test_unknown_offer_rejected_before_campaign_created(client, keitaro, campaign_form):
    response = await client.post("/api/campaigns", json={**campaign_form, "offer_id": 999})
    assert response.status_code == 422
    assert response.json()["detail"] == "Оффер #999 не найден в Keitaro"
    assert keitaro.campaigns == {}


async def test_archived_offer_rejected_before_campaign_created(client, keitaro, campaign_form):
    keitaro.offers[0]["state"] = "deleted"
    response = await client.post("/api/campaigns", json=campaign_form)
    assert response.status_code == 422
    assert response.json()["detail"] == "Оффер #101 в архиве Keitaro"
    assert keitaro.campaigns == {}


async def test_campaign_archived_when_stream_fails(client, keitaro, campaign_form):
    keitaro.fail_on_stream_create = True
    response = await client.post("/api/campaigns", json=campaign_form)
    assert response.status_code == 502
    assert response.json()["source"] == "keitaro"
    assert all(c["state"] == "deleted" for c in keitaro.campaigns.values())


async def test_list_returns_all_campaigns(client, keitaro, campaign_form):
    await client.post("/api/campaigns", json=campaign_form)
    await keitaro.create_campaign({"name": "created_in_keitaro", "alias": "other"})

    campaigns = (await client.get("/api/campaigns")).json()
    assert [(c["name"], c["tracked"]) for c in campaigns] == [
        ("created_in_keitaro", False),  # новые сверху
        ("campaign1", True),
    ]


async def test_campaign_detail(client, campaign_form):
    created = (await client.post("/api/campaigns", json=campaign_form)).json()
    keitaro_id = created["record"]["keitaro_id"]

    detail = (await client.get(f"/api/campaigns/{keitaro_id}")).json()
    assert detail["tracked"] is True
    assert len(detail["streams"]) == 2

    assert (await client.get("/api/campaigns/999")).status_code == 404


async def test_delete_campaign(client, keitaro, campaign_form, session):
    created = (await client.post("/api/campaigns", json=campaign_form)).json()["record"]
    keitaro_id = created["keitaro_id"]
    await client.get(f"/api/campaigns/{keitaro_id}")  # открыли редактор — есть состояние потока
    assert await session.get(StreamState, 1) is not None

    response = await client.delete(f"/api/campaigns/{keitaro_id}")
    assert response.status_code == 204

    assert keitaro.campaigns[keitaro_id]["state"] == "deleted"  # в Keitaro — в архиве
    assert (await client.get("/api/campaigns")).json() == []
    session.expire_all()
    assert await session.get(Campaign, created["id"]) is None
    assert (await session.scalars(select(StreamState))).all() == []

    assert (await client.delete("/api/campaigns/999")).status_code == 404


async def test_keitaro_not_configured_returns_503(client):
    from app.api.deps import get_keitaro
    from app.main import app

    app.dependency_overrides.pop(get_keitaro)
    app.state.keitaro = None
    response = await client.get("/api/keitaro/domains")
    assert response.status_code == 503
    assert "KEITARO_URL" in response.json()["detail"]
