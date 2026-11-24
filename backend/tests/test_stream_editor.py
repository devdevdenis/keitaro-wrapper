"""Редактор потоков через API: новые потоки, черновики, Push to KT, Cancel и правки из Keitaro."""

import pytest

from app.services.stream_editor import CONFLICT_MESSAGE


@pytest.fixture
async def campaign(client, campaign_form) -> dict:
    response = await client.post("/api/campaigns", json=campaign_form)
    assert response.status_code == 201, response.text
    return response.json()


async def open_editor(client, campaign) -> list[dict]:
    response = await client.get(f"/api/campaigns/{campaign['id']}")
    assert response.status_code == 200, response.text
    return response.json()["streams"]


async def stream_named(client, campaign, name: str) -> dict:
    return next(s for s in await open_editor(client, campaign) if s["name"] == name)


def rows(stream: dict) -> list[tuple]:
    return [(o["offer_id"], o["share"], o["status"]) for o in stream["offers"]]


def in_keitaro(keitaro, keitaro_id: int) -> list[tuple[int, int]]:
    return [(o["offer_id"], o["share"]) for o in keitaro.streams[keitaro_id]["offers"]]


def set_keitaro_offers(keitaro, keitaro_id: int, offers: list[tuple[int, int]]) -> None:
    """Правка потока напрямую в Keitaro."""
    keitaro.streams[keitaro_id]["offers"] = [
        {"id": i, "stream_id": keitaro_id, "offer_id": oid, "share": share, "state": "active"}
        for i, (oid, share) in enumerate(offers, 1)
    ]


async def new_stream(client, campaign, kind: str = "regular") -> dict:
    """Новый поток «+ Добавить поток» — шаблон, которого в Keitaro ещё нет."""
    stream = (await client.post(f"/api/campaigns/{campaign['id']}/streams")).json()
    if kind != stream["kind"]:
        stream = (await client.patch(f"/api/streams/{stream['id']}", json={"kind": kind})).json()
    return stream


@pytest.fixture
async def regular(client, campaign) -> dict:
    """Обычный поток Flow 2 — создан вместе с кампанией: оффер 101 (100 %)."""
    return await stream_named(client, campaign, "Flow 2")


@pytest.fixture
async def intercept(client, campaign) -> dict:
    """Перехватывающий поток Flow 1 — создан вместе с кампанией: DE → Google."""
    return await stream_named(client, campaign, "Flow 1")


# --- перехватывающий поток -----------------------------------------------------


async def test_new_intercept_stream_is_published_on_push(client, keitaro, campaign):
    stream = await new_stream(client, campaign, "intercept")
    assert stream["name"] == "Flow 3"
    assert stream["problem"].startswith("Выберите хотя бы одну страну")

    edited = (
        await client.patch(f"/api/streams/{stream['id']}", json={"countries": ["dz", "AO", "dz"]})
    ).json()
    assert edited["countries"] == ["DZ", "AO"]
    assert edited["can_push"] is True
    assert len(keitaro.streams) == 2  # до Push to KT нового потока в Keitaro нет

    pushed = (await client.post(f"/api/streams/{stream['id']}/push")).json()
    assert pushed["is_new"] is False
    assert pushed["has_draft"] is False

    created = keitaro.streams[pushed["keitaro_id"]]
    assert created["campaign_id"] == campaign["id"]
    assert (created["name"], created["type"], created["schema"]) == ("Flow 3", "forced", "redirect")
    assert created["action_payload"] == "https://www.google.com"
    assert created["filter_or"] is True
    assert [(f["name"], f["mode"], f["payload"]) for f in created["filters"]] == [
        ("country", "accept", ["DZ", "AO"])
    ]


async def test_filter_logic_is_or_for_new_and_kept_for_existing(
    client, keitaro, campaign, intercept
):
    kid = intercept["keitaro_id"]
    assert keitaro.streams[kid]["filter_or"] is True  # новый поток — «ИЛИ»

    # в Keitaro логику поменяли на «И» — редактор её не трогает
    keitaro.streams[kid]["filter_or"] = False
    await open_editor(client, campaign)
    await client.patch(f"/api/streams/{intercept['id']}", json={"countries": ["FR"]})
    await client.post(f"/api/streams/{intercept['id']}/push")
    assert keitaro.streams[kid]["filter_or"] is False
    assert keitaro.streams[kid]["filters"][-1]["payload"] == ["FR"]

    ignored = await client.patch(f"/api/streams/{intercept['id']}", json={"filter_or": True})
    assert "filter_or" not in ignored.json()


async def test_intercept_needs_valid_redirect(client, campaign):
    stream = await stream_named(client, campaign, "Flow 1")
    await client.patch(f"/api/streams/{stream['id']}", json={"countries": ["DE"]})
    edited = (
        await client.patch(f"/api/streams/{stream['id']}", json={"redirect_url": "google.com"})
    ).json()
    assert edited["problem"].startswith("Укажите адрес редиректа")
    assert (await client.post(f"/api/streams/{stream['id']}/push")).status_code == 422


async def test_unknown_country_rejected(client, campaign):
    stream = await stream_named(client, campaign, "Flow 1")
    response = await client.patch(f"/api/streams/{stream['id']}", json={"countries": ["DE", "ZZ"]})
    assert response.status_code == 422
    assert response.json()["detail"] == "Неизвестный код страны: ZZ"


async def test_geo_fields_only_for_intercept(client, campaign):
    stream = await stream_named(client, campaign, "Flow 2")
    response = await client.patch(f"/api/streams/{stream['id']}", json={"countries": ["DE"]})
    assert response.status_code == 400


async def test_published_stream_edits_go_through_draft(client, keitaro, campaign, intercept):
    kid = intercept["keitaro_id"]
    # в Keitaro у потока есть ещё фильтр, которым редактор не управляет
    keitaro.streams[kid]["filters"].append({"name": "os", "mode": "accept", "payload": ["iOS"]})
    await open_editor(client, campaign)

    edited = (
        await client.patch(
            f"/api/streams/{intercept['id']}",
            json={"name": "Geo block", "redirect_url": "https://example.com", "countries": ["FR"]},
        )
    ).json()
    assert edited["has_draft"] is True
    assert keitaro.streams[kid]["name"] == "Flow 1"  # до Push to KT Keitaro не меняется

    await client.post(f"/api/streams/{intercept['id']}/push")
    updated = keitaro.streams[kid]
    assert (updated["name"], updated["action_payload"]) == ("Geo block", "https://example.com")
    assert [(f["name"], f["payload"]) for f in updated["filters"]] == [
        ("os", ["iOS"]),
        ("country", ["FR"]),
    ]


async def test_cancel_restores_published_stream(client, keitaro, campaign, intercept):
    await client.patch(f"/api/streams/{intercept['id']}", json={"name": "Renamed"})
    cancelled = (await client.delete(f"/api/streams/{intercept['id']}/draft")).json()
    assert cancelled["name"] == "Flow 1"
    assert cancelled["has_draft"] is False


async def test_cancel_on_template_is_rejected(client, campaign):
    stream = await new_stream(client, campaign)
    assert (await client.delete(f"/api/streams/{stream['id']}/draft")).status_code == 400


# --- добавление и удаление потоков -------------------------------------------


async def test_add_stream_gets_next_flow_name(client, campaign):
    response = await client.post(
        f"/api/campaigns/{campaign['id']}/streams", json={"kind": "regular"}
    )
    assert response.status_code == 201
    added = response.json()
    assert (added["name"], added["kind"], added["position"]) == ("Flow 3", "regular", 3)

    flow1 = await stream_named(client, campaign, "Flow 1")
    await client.delete(f"/api/streams/{flow1['id']}")
    again = (
        await client.post(f"/api/campaigns/{campaign['id']}/streams", json={"kind": "intercept"})
    ).json()
    assert again["name"] == "Flow 4"  # Flow 2 и Flow 3 заняты
    assert again["redirect_url"] == "https://www.google.com"

    missing = await client.post("/api/campaigns/999/streams", json={"kind": "regular"})
    assert missing.status_code == 404


async def test_new_stream_type_is_chosen_in_the_stream(client, campaign, intercept):
    added = (await client.post(f"/api/campaigns/{campaign['id']}/streams")).json()
    assert (added["name"], added["kind"]) == ("Flow 3", "regular")  # по умолчанию — обычный

    await client.patch(f"/api/streams/{added['id']}", json={"name": "Geo"})
    switched = (
        await client.patch(f"/api/streams/{added['id']}", json={"kind": "intercept"})
    ).json()
    assert (switched["name"], switched["kind"], switched["type"]) == ("Geo", "intercept", "forced")
    assert switched["redirect_url"] == "https://www.google.com"

    back = (await client.patch(f"/api/streams/{added['id']}", json={"kind": "regular"})).json()
    assert (back["kind"], back["offers"], back["name"]) == ("regular", [], "Geo")

    # у опубликованного потока тип не меняется
    response = await client.patch(f"/api/streams/{intercept['id']}", json={"kind": "regular"})
    assert response.status_code == 400


async def test_delete_template_and_published_stream(client, keitaro, campaign, intercept):
    template = await new_stream(client, campaign)
    assert (await client.delete(f"/api/streams/{template['id']}")).status_code == 204

    assert (await client.delete(f"/api/streams/{intercept['id']}")).status_code == 204
    assert keitaro.streams[intercept["keitaro_id"]]["state"] == "deleted"
    assert [s["name"] for s in await open_editor(client, campaign)] == ["Flow 2"]
    assert (await client.delete(f"/api/streams/{intercept['id']}")).status_code == 404


async def test_stream_deleted_in_keitaro_disappears(client, keitaro, campaign, intercept):
    keitaro.streams[intercept["keitaro_id"]]["state"] = "deleted"
    assert [s["name"] for s in await open_editor(client, campaign)] == ["Flow 2"]


async def test_other_streams_are_read_only(client, keitaro, campaign):
    await keitaro.create_stream(
        {"campaign_id": campaign["id"], "name": "Action", "type": "regular", "schema": "action"}
    )
    other = await stream_named(client, campaign, "Action")
    assert other["kind"] == "other"
    response = await client.patch(f"/api/streams/{other['id']}", json={"name": "x"})
    assert response.status_code == 400


# --- офферы обычного потока --------------------------------------------------


async def test_new_regular_stream_needs_offers(client, campaign):
    stream = await new_stream(client, campaign)
    assert stream["problem"] == "Добавьте хотя бы один оффер."


async def test_regular_stream_created_with_campaign(client, keitaro, regular):
    created = keitaro.streams[regular["keitaro_id"]]
    assert (created["name"], created["type"], created["schema"]) == (
        "Flow 2",
        "regular",
        "landings",
    )
    assert in_keitaro(keitaro, regular["keitaro_id"]) == [(101, 100)]
    assert rows(regular) == [(101, 100, "active")]
    assert (regular["is_new"], regular["has_draft"]) == (False, False)


async def test_offer_changes_stay_in_draft_until_push(client, keitaro, campaign, regular):
    sid, kid = regular["id"], regular["keitaro_id"]
    edited = (await client.post(f"/api/streams/{sid}/offers", json={"offer_id": 102})).json()
    assert rows(edited) == [(101, 50, "active"), (102, 50, "new")]
    assert edited["offers"][0]["published_share"] == 100
    assert edited["can_push"] is True
    assert in_keitaro(keitaro, kid) == [(101, 100)]

    # черновик переживает повторное открытие редактора
    assert await stream_named(client, campaign, "Flow 2") == edited

    pushed = (await client.post(f"/api/streams/{sid}/push")).json()
    assert rows(pushed) == [(101, 50, "active"), (102, 50, "active")]
    assert in_keitaro(keitaro, kid) == [(101, 50), (102, 50)]


async def test_removed_offer_stays_grey_after_push(client, keitaro, campaign, regular):
    sid, kid = regular["id"], regular["keitaro_id"]
    await client.post(f"/api/streams/{sid}/offers", json={"offer_id": 102})
    await client.post(f"/api/streams/{sid}/push")

    edited = (await client.delete(f"/api/streams/{sid}/offers/101")).json()
    assert rows(edited) == [(101, 0, "removed"), (102, 100, "active")]
    pushed = (await client.post(f"/api/streams/{sid}/push")).json()
    assert rows(pushed) == [(101, 0, "removed"), (102, 100, "active")]
    assert in_keitaro(keitaro, kid) == [(102, 100)]

    reopened = await stream_named(client, campaign, "Flow 2")
    assert rows(reopened) == [(101, 0, "removed"), (102, 100, "active")]

    restored = (await client.post(f"/api/streams/{sid}/offers/101/restore")).json()
    assert rows(restored) == [(101, 50, "new"), (102, 50, "active")]


async def test_forget_removed_offer(client, keitaro, campaign, regular):
    sid, kid = regular["id"], regular["keitaro_id"]
    await client.post(f"/api/streams/{sid}/offers", json={"offer_id": 102})
    await client.post(f"/api/streams/{sid}/offers", json={"offer_id": 103})
    await client.post(f"/api/streams/{sid}/push")

    # удалён и опубликован — в Keitaro его нет: убираем из списка без черновика
    await client.delete(f"/api/streams/{sid}/offers/101")
    await client.post(f"/api/streams/{sid}/push")
    forgotten = (await client.delete(f"/api/streams/{sid}/offers/101/row")).json()
    assert [o["offer_id"] for o in forgotten["offers"]] == [102, 103]
    assert forgotten["has_draft"] is False
    assert [o["offer_id"] for o in (await stream_named(client, campaign, "Flow 2"))["offers"]] == [
        102,
        103,
    ]

    # удалён только в черновике — уйдёт из Keitaro по Push to KT
    await client.delete(f"/api/streams/{sid}/offers/103")
    edited = (await client.delete(f"/api/streams/{sid}/offers/103/row")).json()
    assert rows(edited) == [(102, 100, "active")]
    assert edited["has_draft"] is True
    await client.post(f"/api/streams/{sid}/push")
    assert in_keitaro(keitaro, kid) == [(102, 100)]

    active = await client.delete(f"/api/streams/{sid}/offers/102/row")
    assert active.status_code == 409


async def test_cancel_discards_offer_draft(client, keitaro, regular):
    sid = regular["id"]
    await client.post(f"/api/streams/{sid}/offers", json={"offer_id": 102})
    await client.put(f"/api/streams/{sid}/offers/101/pin", json={"pinned": True})

    cancelled = (await client.delete(f"/api/streams/{sid}/draft")).json()
    assert rows(cancelled) == [(101, 100, "active")]
    assert cancelled["offers"][0]["pinned"] is False
    assert cancelled["has_draft"] is False


async def test_undoing_changes_drops_draft(client, keitaro, campaign, regular):
    set_keitaro_offers(keitaro, regular["keitaro_id"], [(101, 50), (102, 50)])
    await open_editor(client, campaign)

    await client.delete(f"/api/streams/{regular['id']}/offers/101")
    restored = (await client.post(f"/api/streams/{regular['id']}/offers/101/restore")).json()
    assert rows(restored) == [(101, 50, "active"), (102, 50, "active")]
    assert restored["has_draft"] is False


async def test_pinned_share_survives_add_and_push(client, keitaro, campaign, regular):
    sid, kid = regular["id"], regular["keitaro_id"]
    set_keitaro_offers(keitaro, kid, [(101, 34), (102, 33), (103, 33)])
    await open_editor(client, campaign)

    await client.put(f"/api/streams/{sid}/offers/101/pin", json={"pinned": True})
    edited = (await client.post(f"/api/streams/{sid}/offers", json={"offer_id": 104})).json()
    assert [o["share"] for o in edited["offers"]] == [34, 22, 22, 22]

    pushed = (await client.post(f"/api/streams/{sid}/push")).json()
    assert pushed["offers"][0]["pinned"] is True
    assert in_keitaro(keitaro, kid) == [(101, 34), (102, 22), (103, 22), (104, 22)]


async def test_push_blocked_when_all_offers_removed(client, keitaro, regular):
    edited = (await client.delete(f"/api/streams/{regular['id']}/offers/101")).json()
    assert edited["can_push"] is False
    assert "Удалены все офферы" in edited["problem"]
    assert (await client.post(f"/api/streams/{regular['id']}/push")).status_code == 422
    assert in_keitaro(keitaro, regular["keitaro_id"]) == [(101, 100)]


async def test_push_blocked_when_free_share_has_no_owner(client, keitaro, campaign, regular):
    sid = regular["id"]
    set_keitaro_offers(keitaro, regular["keitaro_id"], [(101, 50), (102, 30), (103, 20)])
    await open_editor(client, campaign)
    await client.put(f"/api/streams/{sid}/offers/101/pin", json={"pinned": True})
    await client.put(f"/api/streams/{sid}/offers/102/pin", json={"pinned": True})

    edited = (await client.delete(f"/api/streams/{sid}/offers/103")).json()
    assert [o["share"] for o in edited["offers"]] == [50, 30, 0]
    assert edited["problem"].startswith("20 % трафика некому отдать")

    unpinned = (
        await client.put(f"/api/streams/{sid}/offers/102/pin", json={"pinned": False})
    ).json()
    assert [o["share"] for o in unpinned["offers"]] == [50, 50, 0]
    assert unpinned["can_push"] is True


async def test_keitaro_changes_are_pulled_on_open(client, keitaro, campaign, regular):
    await client.put(f"/api/streams/{regular['id']}/offers/101/pin", json={"pinned": True})
    await client.post(f"/api/streams/{regular['id']}/push")

    set_keitaro_offers(keitaro, regular["keitaro_id"], [(102, 60), (103, 40)])
    keitaro.streams[regular["keitaro_id"]]["name"] = "Renamed in Keitaro"
    stream = await stream_named(client, campaign, "Renamed in Keitaro")
    assert rows(stream) == [(101, 0, "removed"), (102, 60, "active"), (103, 40, "active")]
    assert stream["offers"][0]["pinned"] is False


async def test_keitaro_change_during_draft_blocks_push(client, keitaro, campaign, regular):
    sid, kid = regular["id"], regular["keitaro_id"]
    await client.post(f"/api/streams/{sid}/offers", json={"offer_id": 102})
    set_keitaro_offers(keitaro, kid, [(101, 70), (103, 30)])

    response = await client.post(f"/api/streams/{sid}/push")
    assert response.status_code == 409
    assert response.json()["detail"] == CONFLICT_MESSAGE
    assert in_keitaro(keitaro, kid) == [(101, 70), (103, 30)]

    stream = await stream_named(client, campaign, "Flow 2")
    assert stream["conflict"] is True
    assert stream["can_push"] is False
    assert rows(stream) == [(101, 50, "active"), (102, 50, "new")]  # черновик не потерян

    cancelled = (await client.delete(f"/api/streams/{sid}/draft")).json()
    assert rows(cancelled) == [(101, 70, "active"), (103, 30, "active")]
    assert cancelled["conflict"] is False


async def test_conflict_on_stream_fields(client, keitaro, campaign, intercept):
    await client.patch(f"/api/streams/{intercept['id']}", json={"name": "Mine"})
    keitaro.streams[intercept["keitaro_id"]]["action_payload"] = "https://changed.example"

    stream = await stream_named(client, campaign, "Mine")
    assert stream["conflict"] is True
    assert stream["problem"] == CONFLICT_MESSAGE


async def test_add_validates_offer(client, regular):
    response = await client.post(f"/api/streams/{regular['id']}/offers", json={"offer_id": 999})
    assert response.status_code == 422
    assert response.json()["detail"] == "Оффер #999 не найден в Keitaro"
    duplicate = await client.post(f"/api/streams/{regular['id']}/offers", json={"offer_id": 101})
    assert duplicate.status_code == 409


async def test_offers_only_in_regular_stream(client, campaign):
    stream = await stream_named(client, campaign, "Flow 1")
    response = await client.post(f"/api/streams/{stream['id']}/offers", json={"offer_id": 101})
    assert response.status_code == 400


async def test_restore_of_archived_offer_rejected(client, keitaro, regular):
    sid = regular["id"]
    await client.post(f"/api/streams/{sid}/offers", json={"offer_id": 102})
    await client.delete(f"/api/streams/{sid}/offers/101")
    await client.post(f"/api/streams/{sid}/push")
    keitaro.offers[0]["state"] = "deleted"  # оффер 101 ушёл в архив

    response = await client.post(f"/api/streams/{sid}/offers/101/restore")
    assert response.status_code == 422
    assert response.json()["detail"] == "Оффер #101 в архиве Keitaro"


async def test_push_without_draft(client, regular):
    assert (await client.post(f"/api/streams/{regular['id']}/push")).status_code == 409


async def test_unknown_stream(client):
    response = await client.post("/api/streams/999/offers", json={"offer_id": 101})
    assert response.status_code == 404


# --- Push to KT для всей кампании --------------------------------------------


async def test_push_campaign_publishes_all_drafts(client, keitaro, campaign, intercept, regular):
    await client.patch(f"/api/streams/{intercept['id']}", json={"countries": ["FR"]})
    await client.post(f"/api/streams/{regular['id']}/offers", json={"offer_id": 102})
    added = await new_stream(client, campaign)
    await client.post(f"/api/streams/{added['id']}/offers", json={"offer_id": 103})

    response = await client.post(f"/api/campaigns/{campaign['id']}/push")
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["published"], body["failed_stream_id"]) == (3, None)
    assert [(s["name"], s["has_draft"], s["is_new"]) for s in body["streams"]] == [
        ("Flow 1", False, False),
        ("Flow 2", False, False),
        ("Flow 3", False, False),
    ]
    assert keitaro.streams[intercept["keitaro_id"]]["filters"][0]["payload"] == ["FR"]
    assert in_keitaro(keitaro, regular["keitaro_id"]) == [(101, 50), (102, 50)]


async def test_push_campaign_blocked_by_any_problem(client, keitaro, campaign, intercept):
    await client.patch(f"/api/streams/{intercept['id']}", json={"countries": ["FR"]})
    await new_stream(client, campaign)  # Flow 3 без офферов

    response = await client.post(f"/api/campaigns/{campaign['id']}/push")
    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Нельзя опубликовать: «Flow 3» — Добавьте хотя бы один оффер."
    )
    # готовый Flow 1 тоже не опубликован
    assert keitaro.streams[intercept["keitaro_id"]]["filters"][0]["payload"] == ["DE"]


async def test_push_campaign_blocked_by_keitaro_change(client, keitaro, campaign, intercept):
    await client.patch(f"/api/streams/{intercept['id']}", json={"name": "Mine"})
    added = await new_stream(client, campaign)
    await client.post(f"/api/streams/{added['id']}/offers", json={"offer_id": 101})
    keitaro.streams[intercept["keitaro_id"]]["action_payload"] = "https://changed.example"

    response = await client.post(f"/api/campaigns/{campaign['id']}/push")
    assert response.status_code == 409
    assert "«Mine»" in response.json()["detail"]
    assert len(keitaro.streams) == 2  # Flow 3 тоже не создан
    assert keitaro.streams[intercept["keitaro_id"]]["name"] == "Flow 1"


async def test_push_campaign_stops_on_keitaro_error(client, keitaro, campaign, intercept):
    await client.patch(f"/api/streams/{intercept['id']}", json={"name": "Geo block"})
    added = await new_stream(client, campaign)
    await client.post(f"/api/streams/{added['id']}/offers", json={"offer_id": 101})
    keitaro.fail_on_stream_create = True  # Flow 3 создать не получится

    body = (await client.post(f"/api/campaigns/{campaign['id']}/push")).json()
    assert body["published"] == 1
    assert body["failed_stream_id"] == added["id"]
    assert body["error"] == "Stream creation failed (fake)"
    # Flow 1 уже опубликован, Flow 3 остался черновиком
    assert keitaro.streams[intercept["keitaro_id"]]["name"] == "Geo block"
    states = {s["name"]: s for s in body["streams"]}
    assert states["Geo block"]["has_draft"] is False
    assert states["Flow 3"]["has_draft"] is True


async def test_push_campaign_without_drafts(client, keitaro, campaign, intercept, regular):
    response = await client.post(f"/api/campaigns/{campaign['id']}/push")
    assert response.status_code == 409
