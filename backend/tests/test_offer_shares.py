"""Правила пересчёта долей — примеры из docs/campaign-editor.md."""

import pytest

from app.keitaro.payloads import stream_offers_payload
from app.services import offer_shares as rules
from app.services.errors import ServiceError
from app.services.offer_shares import Offer

A, B, C, D = 1, 2, 3, 4


def shares(offers: list[Offer]) -> list[tuple[int, int]]:
    return [(o.offer_id, o.share) for o in offers]


def test_split_shares():
    assert rules.split_shares(3) == [34, 33, 33]
    assert sum(rules.split_shares(7)) == 100
    assert rules.split_shares(3, 66) == [22, 22, 22]
    assert rules.split_shares(2, -10) == [0, 0]
    assert rules.split_shares(0) == []


def test_add_splits_evenly():
    offers = [Offer(A, 34), Offer(B, 33), Offer(C, 33)]
    assert shares(rules.add_offer(offers, D)) == [(A, 25), (B, 25), (C, 25), (D, 25)]


def test_add_keeps_pinned_share():
    offers = [Offer(A, 34, pinned=True), Offer(B, 33), Offer(C, 33)]
    assert shares(rules.add_offer(offers, D)) == [(A, 34), (B, 22), (C, 22), (D, 22)]


def test_remove_gives_zero_and_rebalances_the_rest():
    offers = [Offer(A, 34, pinned=True), Offer(B, 22), Offer(C, 22), Offer(D, 22)]
    result = rules.remove_offer(offers, C)
    assert shares(result) == [(A, 34), (B, 33), (C, 0), (D, 33)]
    assert result[2].removed


def test_extra_percent_goes_to_first_offers():
    offers = [Offer(A, 50), Offer(B, 50)]
    assert shares(rules.add_offer(offers, C)) == [(A, 34), (B, 33), (C, 33)]


def test_bring_back_restores_previous_split():
    offers = [Offer(A, 34), Offer(B, 33), Offer(C, 33)]
    removed = rules.remove_offer(offers, C)
    assert shares(removed) == [(A, 50), (B, 50), (C, 0)]
    assert rules.restore_offer(removed, C) == offers


def test_removing_pinned_offer_unpins_it():
    offers = [Offer(A, 34, pinned=True), Offer(B, 33), Offer(C, 33)]
    result = rules.remove_offer(offers, A)
    assert shares(result) == [(A, 0), (B, 50), (C, 50)]
    assert not result[0].pinned


def test_pin_does_not_touch_shares_unpin_rebalances():
    offers = [Offer(A, 70), Offer(B, 20), Offer(C, 10)]
    pinned = rules.pin_offer(offers, A, True)
    assert shares(pinned) == shares(offers)
    assert pinned[0].pinned
    assert shares(rules.pin_offer(pinned, A, False)) == [(A, 34), (B, 33), (C, 33)]


def test_all_removed_blocks_publishing():
    offers = rules.remove_offer([Offer(A, 100)], A)
    assert "Удалены все офферы" in rules.publish_problem(offers)


def test_free_share_without_owner_blocks_publishing():
    offers = [Offer(A, 50, pinned=True), Offer(B, 30, pinned=True), Offer(C, 20)]
    result = rules.remove_offer(offers, C)
    assert shares(result) == [(A, 50), (B, 30), (C, 0)]
    assert rules.publish_problem(result).startswith("20 % трафика некому отдать")

    # снимаем закрепление с B — он забирает свободные 20 %
    unpinned = rules.pin_offer(result, B, False)
    assert shares(unpinned) == [(A, 50), (B, 50), (C, 0)]
    assert rules.publish_problem(unpinned) is None


def test_errors():
    offers = [Offer(A, 50), Offer(B, 50, removed=True)]
    with pytest.raises(ServiceError, match="уже есть"):
        rules.add_offer(offers, A)
    with pytest.raises(ServiceError, match="Bring Back"):
        rules.add_offer(offers, B)
    with pytest.raises(ServiceError, match="нет в потоке"):
        rules.remove_offer(offers, C)
    with pytest.raises(ServiceError, match="удалённого"):
        rules.pin_offer(offers, B, True)


def test_reconcile_with_keitaro():
    saved = [Offer(A, 50, pinned=True), Offer(B, 50), Offer(C, 0, removed=True)]
    keitaro = [{"offer_id": A, "share": 60}, {"offer_id": D, "share": 40}]
    assert rules.reconcile(saved, keitaro) == [
        Offer(A, 60, pinned=True),  # доля из Keitaro, закрепление осталось
        Offer(B, 0, removed=True),  # удалён в Keitaro
        Offer(C, 0, removed=True),  # был удалён раньше
        Offer(D, 40),  # добавлен в Keitaro
    ]


def test_signature_ignores_removed_and_order():
    first = [Offer(B, 50), Offer(A, 50), Offer(C, 0, removed=True)]
    second = [Offer(A, 50, pinned=True), Offer(B, 50)]
    assert rules.signature(first) == rules.signature(second) == [[A, 50], [B, 50]]


def test_offers_payload_keeps_keitaro_state():
    current = [{"offer_id": A, "share": 100, "state": "disabled"}]
    assert stream_offers_payload([(A, 50), (B, 50)], current) == [
        {"offer_id": A, "share": 50, "state": "disabled"},
        {"offer_id": B, "share": 50, "state": "active"},
    ]
