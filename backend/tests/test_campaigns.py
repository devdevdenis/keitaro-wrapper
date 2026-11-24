from sqlalchemy import select

from app.models import Campaign, StreamState


async def create(client, form: dict) -> dict:
    response = await client.post("/api/campaigns", json=form)
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_campaign_without_streams(client, keitaro, campaign_form, session):
    campaign = await create(client, campaign_form)

    assert campaign["name"] == "campaign1"
    assert campaign["tracked"] is True
    created = keitaro.campaigns[campaign["id"]]
    assert (created["domain_id"], created["group_id"], created["traffic_source_id"]) == (1, 1, 1)

    # в Keitaro потоков нет — только шаблоны в редакторе
    assert keitaro.streams == {}
    record = await session.scalar(select(Campaign).where(Campaign.keitaro_id == campaign["id"]))
    assert record is not None


async def test_new_campaign_gets_two_stream_templates(client, campaign_form):
    campaign = await create(client, campaign_form)
    detail = (await client.get(f"/api/campaigns/{campaign['id']}")).json()

    intercept, regular = detail["streams"]
    assert (intercept["name"], intercept["kind"], intercept["type"]) == (
        "Flow 1",
        "intercept",
        "forced",
    )
    assert intercept["redirect_url"] == "https://www.google.com"
    assert intercept["countries"] == []
    assert (regular["name"], regular["kind"], regular["offers"]) == ("Flow 2", "regular", [])
    for stream in (intercept, regular):
        assert stream["is_new"] is True
        assert stream["keitaro_id"] is None
        assert stream["has_draft"] is True
        assert stream["can_push"] is False  # шаблон надо заполнить


async def test_name_is_taken_as_is(client, keitaro, campaign_form):
    campaign = await create(client, {**campaign_form, "name": "  Nutra DE  "})
    assert campaign["name"] == "Nutra DE"  # только обрезаны пробелы
    assert keitaro.campaigns[campaign["id"]]["name"] == "Nutra DE"


async def test_create_requires_all_fields(client, campaign_form):
    for field in campaign_form:
        form = {k: v for k, v in campaign_form.items() if k != field}
        assert (await client.post("/api/campaigns", json=form)).status_code == 422, field
    response = await client.post("/api/campaigns", json={**campaign_form, "name": "   "})
    assert response.status_code == 422


async def test_update_campaign_goes_to_keitaro(client, keitaro, campaign_form, session):
    campaign = await create(client, campaign_form)
    form = {"name": "Renamed", "domain_id": 2, "group_id": 2, "traffic_source_id": 3}

    response = await client.put(f"/api/campaigns/{campaign['id']}", json=form)
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Renamed"

    updated = keitaro.campaigns[campaign["id"]]
    assert (updated["name"], updated["domain_id"], updated["traffic_source_id"]) == (
        "Renamed",
        2,
        3,
    )
    record = await session.scalar(select(Campaign).where(Campaign.keitaro_id == campaign["id"]))
    assert (record.name, record.group_id) == ("Renamed", 2)

    assert (await client.put("/api/campaigns/999", json=form)).status_code == 404


async def test_list_returns_all_campaigns(client, keitaro, campaign_form):
    await create(client, campaign_form)
    await keitaro.create_campaign({"name": "created_in_keitaro", "alias": "other"})

    campaigns = (await client.get("/api/campaigns")).json()
    assert [(c["name"], c["tracked"]) for c in campaigns] == [
        ("created_in_keitaro", False),  # новые сверху
        ("campaign1", True),
    ]


async def test_list_shows_published_geo(client, campaign_form):
    campaign = await create(client, campaign_form)
    intercept = (await client.get(f"/api/campaigns/{campaign['id']}")).json()["streams"][0]
    await client.patch(f"/api/streams/{intercept['id']}", json={"countries": ["de", "at"]})

    listed = (await client.get("/api/campaigns")).json()
    assert listed[0]["country_codes"] == []  # черновик ещё не опубликован

    await client.post(f"/api/streams/{intercept['id']}/push")
    listed = (await client.get("/api/campaigns")).json()
    assert listed[0]["country_codes"] == ["DE", "AT"]


async def test_campaign_detail(client, campaign_form):
    campaign = await create(client, campaign_form)
    detail = (await client.get(f"/api/campaigns/{campaign['id']}")).json()
    assert detail["tracked"] is True
    assert detail["record"]["name"] == "campaign1"
    assert (await client.get("/api/campaigns/999")).status_code == 404


async def test_delete_campaign(client, keitaro, campaign_form, session):
    campaign = await create(client, campaign_form)
    assert (await session.scalars(select(StreamState))).all()  # шаблоны потоков

    response = await client.delete(f"/api/campaigns/{campaign['id']}")
    assert response.status_code == 204

    assert keitaro.campaigns[campaign["id"]]["state"] == "deleted"  # в Keitaro — в архиве
    assert (await client.get("/api/campaigns")).json() == []
    session.expire_all()
    assert (await session.scalars(select(Campaign))).all() == []
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
