"""Редактор офферов через API: черновик, Push to KT, Cancel и правки из Keitaro."""

import pytest

from app.services.stream_editor import CONFLICT_MESSAGE


@pytest.fixture
async def campaign(client, campaign_form) -> dict:
    created = (await client.post("/api/campaigns", json=campaign_form)).json()
    return created["record"]


@pytest.fixture
def stream_id(campaign) -> int:
    return campaign["offer_stream_id"]


async def open_editor(client, campaign) -> dict[int, dict]:
    response = await client.get(f"/api/campaigns/{campaign['keitaro_id']}")
    assert response.status_code == 200, response.text
    return {s["id"]: s for s in response.json()["streams"]}


def rows(editor: dict) -> list[tuple]:
    return [(o["offer_id"], o["share"], o["status"]) for o in editor["offers"]]


def in_keitaro(keitaro, stream_id: int) -> list[tuple[int, int]]:
    return [(o["offer_id"], o["share"]) for o in keitaro.streams[stream_id]["offers"]]


def set_keitaro_offers(keitaro, stream_id: int, offers: list[tuple[int, int]]) -> None:
    """Правка потока напрямую в Keitaro."""
    keitaro.streams[stream_id]["offers"] = [
        {"id": i, "stream_id": stream_id, "offer_id": oid, "share": share, "state": "active"}
        for i, (oid, share) in enumerate(offers, 1)
    ]


async def test_only_offer_streams_are_editable(client, campaign, stream_id):
    streams = await open_editor(client, campaign)
    google = streams[campaign["google_stream_id"]]
    assert google["name"].startswith("Google")
    assert google["editor"] is None

    editor = streams[stream_id]["editor"]
    assert rows(editor) == [(101, 100, "active")]
    assert editor["has_draft"] is False
    assert editor["can_push"] is False

    response = await client.post(
        f"/api/streams/{campaign['google_stream_id']}/offers", json={"offer_id": 102}
    )
    assert response.status_code == 400


async def test_changes_stay_in_draft_until_push(client, keitaro, campaign, stream_id):
    editor = (await client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": 102})).json()
    assert rows(editor) == [(101, 50, "active"), (102, 50, "new")]
    assert editor["offers"][0]["published_share"] == 100
    assert editor["has_draft"] is True
    assert editor["can_push"] is True
    assert in_keitaro(keitaro, stream_id) == [(101, 100)]

    # черновик переживает повторное открытие редактора
    assert (await open_editor(client, campaign))[stream_id]["editor"] == editor

    pushed = (await client.post(f"/api/streams/{stream_id}/push")).json()
    assert rows(pushed) == [(101, 50, "active"), (102, 50, "active")]
    assert pushed["has_draft"] is False
    assert in_keitaro(keitaro, stream_id) == [(101, 50), (102, 50)]


async def test_removed_offer_stays_grey_after_push(client, keitaro, campaign, stream_id):
    await client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": 102})
    await client.post(f"/api/streams/{stream_id}/push")

    editor = (await client.delete(f"/api/streams/{stream_id}/offers/101")).json()
    assert rows(editor) == [(101, 0, "removed"), (102, 100, "active")]
    assert editor["offers"][0]["removed"] is True

    pushed = (await client.post(f"/api/streams/{stream_id}/push")).json()
    assert rows(pushed) == [(101, 0, "removed"), (102, 100, "active")]
    assert in_keitaro(keitaro, stream_id) == [(102, 100)]

    # и после повторного открытия удалённый оффер на месте — его можно вернуть
    editor = (await open_editor(client, campaign))[stream_id]["editor"]
    assert rows(editor) == [(101, 0, "removed"), (102, 100, "active")]

    restored = (await client.post(f"/api/streams/{stream_id}/offers/101/restore")).json()
    assert rows(restored) == [(101, 50, "new"), (102, 50, "active")]
    await client.post(f"/api/streams/{stream_id}/push")
    assert in_keitaro(keitaro, stream_id) == [(101, 50), (102, 50)]


async def test_cancel_discards_draft(client, keitaro, campaign, stream_id):
    await client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": 102})
    await client.put(f"/api/streams/{stream_id}/offers/101/pin", json={"pinned": True})

    editor = (await client.delete(f"/api/streams/{stream_id}/draft")).json()
    assert rows(editor) == [(101, 100, "active")]
    assert editor["offers"][0]["pinned"] is False
    assert editor["has_draft"] is False
    assert in_keitaro(keitaro, stream_id) == [(101, 100)]


async def test_undoing_changes_drops_draft(client, keitaro, campaign, stream_id):
    set_keitaro_offers(keitaro, stream_id, [(101, 50), (102, 50)])
    await open_editor(client, campaign)

    await client.delete(f"/api/streams/{stream_id}/offers/101")
    editor = (await client.post(f"/api/streams/{stream_id}/offers/101/restore")).json()
    assert rows(editor) == [(101, 50, "active"), (102, 50, "active")]
    assert editor["has_draft"] is False


async def test_pinned_share_survives_add_and_push(client, keitaro, campaign, stream_id):
    set_keitaro_offers(keitaro, stream_id, [(101, 34), (102, 33), (103, 33)])
    await open_editor(client, campaign)

    await client.put(f"/api/streams/{stream_id}/offers/101/pin", json={"pinned": True})
    editor = (await client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": 104})).json()
    assert [o["share"] for o in editor["offers"]] == [34, 22, 22, 22]

    pushed = (await client.post(f"/api/streams/{stream_id}/push")).json()
    assert pushed["offers"][0]["pinned"] is True
    assert in_keitaro(keitaro, stream_id) == [(101, 34), (102, 22), (103, 22), (104, 22)]


async def test_push_blocked_when_all_offers_removed(client, keitaro, campaign, stream_id):
    editor = (await client.delete(f"/api/streams/{stream_id}/offers/101")).json()
    assert editor["can_push"] is False
    assert "Удалены все офферы" in editor["problem"]

    response = await client.post(f"/api/streams/{stream_id}/push")
    assert response.status_code == 422
    assert in_keitaro(keitaro, stream_id) == [(101, 100)]


async def test_push_blocked_when_free_share_has_no_owner(client, keitaro, campaign, stream_id):
    set_keitaro_offers(keitaro, stream_id, [(101, 50), (102, 30), (103, 20)])
    await open_editor(client, campaign)
    await client.put(f"/api/streams/{stream_id}/offers/101/pin", json={"pinned": True})
    await client.put(f"/api/streams/{stream_id}/offers/102/pin", json={"pinned": True})

    editor = (await client.delete(f"/api/streams/{stream_id}/offers/103")).json()
    assert [o["share"] for o in editor["offers"]] == [50, 30, 0]
    assert editor["can_push"] is False
    assert editor["problem"].startswith("20 % трафика некому отдать")
    assert (await client.post(f"/api/streams/{stream_id}/push")).status_code == 422

    editor = (
        await client.put(f"/api/streams/{stream_id}/offers/102/pin", json={"pinned": False})
    ).json()
    assert [o["share"] for o in editor["offers"]] == [50, 50, 0]
    assert editor["can_push"] is True


async def test_keitaro_changes_are_pulled_on_open(client, keitaro, campaign, stream_id):
    await client.put(f"/api/streams/{stream_id}/offers/101/pin", json={"pinned": True})
    await client.post(f"/api/streams/{stream_id}/push")

    set_keitaro_offers(keitaro, stream_id, [(102, 60), (103, 40)])
    editor = (await open_editor(client, campaign))[stream_id]["editor"]
    assert rows(editor) == [(101, 0, "removed"), (102, 60, "active"), (103, 40, "active")]
    assert editor["offers"][0]["pinned"] is False


async def test_keitaro_change_during_draft_blocks_push(client, keitaro, campaign, stream_id):
    await open_editor(client, campaign)
    await client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": 102})
    set_keitaro_offers(keitaro, stream_id, [(101, 70), (103, 30)])

    response = await client.post(f"/api/streams/{stream_id}/push")
    assert response.status_code == 409
    assert response.json()["detail"] == CONFLICT_MESSAGE
    assert in_keitaro(keitaro, stream_id) == [(101, 70), (103, 30)]

    editor = (await open_editor(client, campaign))[stream_id]["editor"]
    assert editor["conflict"] is True
    assert editor["can_push"] is False
    assert rows(editor) == [(101, 50, "active"), (102, 50, "new")]  # черновик не потерян

    editor = (await client.delete(f"/api/streams/{stream_id}/draft")).json()
    assert rows(editor) == [(101, 70, "active"), (103, 30, "active")]
    assert editor["conflict"] is False


async def test_conflict_is_shown_on_refresh(client, keitaro, campaign, stream_id):
    await client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": 102})
    set_keitaro_offers(keitaro, stream_id, [(101, 100), (103, 0)])

    editor = (await open_editor(client, campaign))[stream_id]["editor"]
    assert editor["conflict"] is True
    assert editor["problem"] == CONFLICT_MESSAGE


async def test_add_validates_offer(client, keitaro, campaign, stream_id):
    response = await client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": 999})
    assert response.status_code == 422
    assert response.json()["detail"] == "Оффер #999 не найден в Keitaro"

    duplicate = await client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": 101})
    assert duplicate.status_code == 409


async def test_restore_of_archived_offer_rejected(client, keitaro, campaign, stream_id):
    await client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": 102})
    await client.delete(f"/api/streams/{stream_id}/offers/101")
    await client.post(f"/api/streams/{stream_id}/push")
    keitaro.offers[0]["state"] = "deleted"  # оффер 101 ушёл в архив

    response = await client.post(f"/api/streams/{stream_id}/offers/101/restore")
    assert response.status_code == 422
    assert response.json()["detail"] == "Оффер #101 в архиве Keitaro"


async def test_push_without_draft(client, campaign, stream_id):
    response = await client.post(f"/api/streams/{stream_id}/push")
    assert response.status_code == 409


async def test_unknown_stream(client):
    response = await client.post("/api/streams/999/offers", json={"offer_id": 101})
    assert response.status_code == 404
