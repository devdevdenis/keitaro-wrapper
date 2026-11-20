from app.keitaro.payloads import campaign_name, split_shares
from app.models import Campaign


async def test_create_campaign_builds_two_streams(client, keitaro, campaign_form, session):
    response = await client.post("/api/campaigns", json=campaign_form)
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["record"]["name"] == "test_volper_campaign1"
    assert body["record"]["country_code"] == "DE"

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


async def test_prefix_is_not_duplicated():
    assert campaign_name("test_volper_x", "test_volper_") == "test_volper_x"
    assert campaign_name("  x ", "test_volper_") == "test_volper_x"


async def test_unknown_country_rejected(client, campaign_form):
    response = await client.post("/api/campaigns", json={**campaign_form, "country_code": "ZZ"})
    assert response.status_code == 422


async def test_campaign_archived_when_stream_fails(client, keitaro, campaign_form):
    keitaro.fail_on_stream_create = True
    response = await client.post("/api/campaigns", json=campaign_form)
    assert response.status_code == 502
    assert response.json()["source"] == "keitaro"
    assert all(c["state"] == "deleted" for c in keitaro.campaigns.values())


async def test_list_returns_only_prefixed(client, keitaro, campaign_form):
    await client.post("/api/campaigns", json=campaign_form)
    await keitaro.create_campaign({"name": "someone_else", "alias": "other"})

    mine = (await client.get("/api/campaigns")).json()
    assert [c["name"] for c in mine] == ["test_volper_campaign1"]
    assert mine[0]["tracked"] is True

    everything = (await client.get("/api/campaigns", params={"mine": False})).json()
    assert len(everything) == 2


async def test_add_and_remove_offer(client, campaign_form):
    created = (await client.post("/api/campaigns", json=campaign_form)).json()
    stream_id = created["record"]["offer_stream_id"]

    stream = (await client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": 102})).json()
    assert [(o["offer_id"], o["share"]) for o in stream["offers"]] == [(101, 50), (102, 50)]

    duplicate = await client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": 102})
    assert duplicate.status_code == 409

    stream = (await client.delete(f"/api/streams/{stream_id}/offers/101")).json()
    assert [(o["offer_id"], o["share"]) for o in stream["offers"]] == [(102, 100)]

    last = await client.delete(f"/api/streams/{stream_id}/offers/102")
    assert last.status_code == 409


async def test_campaign_detail(client, campaign_form):
    created = (await client.post("/api/campaigns", json=campaign_form)).json()
    keitaro_id = created["record"]["keitaro_id"]

    detail = (await client.get(f"/api/campaigns/{keitaro_id}")).json()
    assert detail["tracked"] is True
    assert len(detail["streams"]) == 2

    assert (await client.get("/api/campaigns/999")).status_code == 404


def test_split_shares():
    assert split_shares(3) == [34, 33, 33]
    assert sum(split_shares(7)) == 100
    assert split_shares(0) == []


async def test_keitaro_not_configured_returns_503(client):
    from app.api.deps import get_keitaro
    from app.main import app

    app.dependency_overrides.pop(get_keitaro)
    app.state.keitaro = None
    response = await client.get("/api/keitaro/domains")
    assert response.status_code == 503
    assert "KEITARO_URL" in response.json()["detail"]
