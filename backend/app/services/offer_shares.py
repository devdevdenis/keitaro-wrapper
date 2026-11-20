"""Правила редактора офферов: список офферов потока и пересчёт долей (docs/campaign-editor.md).

Чистые функции без обращения к БД и Keitaro. Каждая операция возвращает новый список.
"""

from dataclasses import asdict, dataclass, replace

from app.keitaro.client import JSON
from app.services.errors import ServiceError

TOTAL_SHARE = 100


@dataclass(frozen=True)
class Offer:
    """Оффер в списке редактора."""

    offer_id: int
    share: int
    removed: bool = False  # удалён: в Keitaro его нет (или не будет после публикации)
    pinned: bool = False  # доля закреплена и не меняется при пересчётах

    @classmethod
    def from_json(cls, data: JSON) -> "Offer":
        return cls(**data)

    def to_json(self) -> JSON:
        return asdict(self)


def load(data: list[JSON] | None) -> list[Offer]:
    return [Offer.from_json(o) for o in data or []]


def dump(offers: list[Offer]) -> list[JSON]:
    return [o.to_json() for o in offers]


def split_shares(count: int, total: int = TOTAL_SHARE) -> list[int]:
    """Делит `total` поровну между `count` офферами; лишние проценты получают первые."""
    if count <= 0:
        return []
    base, rest = divmod(max(total, 0), count)
    return [base + (1 if i < rest else 0) for i in range(count)]


def rebalance(offers: list[Offer]) -> list[Offer]:
    """Удалённые получают 0 %, закреплённые сохраняют долю, остаток делится поровну."""
    pinned_total = sum(o.share for o in offers if o.pinned and not o.removed)
    free_count = sum(1 for o in offers if not o.pinned and not o.removed)
    shares = iter(split_shares(free_count, TOTAL_SHARE - pinned_total))

    result = []
    for offer in offers:
        if offer.removed:
            result.append(replace(offer, share=0, pinned=False))
        elif offer.pinned:
            result.append(offer)
        else:
            result.append(replace(offer, share=next(shares)))
    return result


def reconcile(saved: list[Offer], keitaro_offers: list[JSON]) -> list[Offer]:
    """Сверяет список редактора с офферами потока в Keitaro.

    Доли берутся из Keitaro. Оффер, которого в Keitaro больше нет, остаётся в списке удалённым;
    оффер, добавленный в Keitaro, дописывается в конец. Закрепления сохраняются.
    """
    in_keitaro = {int(o["offer_id"]): int(o.get("share") or 0) for o in keitaro_offers}
    result = []
    for offer in saved:
        if offer.offer_id in in_keitaro:
            result.append(replace(offer, share=in_keitaro[offer.offer_id], removed=False))
        else:
            result.append(replace(offer, share=0, removed=True, pinned=False))
    known = {o.offer_id for o in saved}
    result += [Offer(oid, share) for oid, share in in_keitaro.items() if oid not in known]
    return result


def signature(offers: list[Offer]) -> list[list[int]]:
    """Что реально стоит в потоке Keitaro: пары [offer_id, share] активных офферов."""
    return sorted([o.offer_id, o.share] for o in offers if not o.removed)


def publish_problem(offers: list[Offer]) -> str | None:
    """Почему такой список нельзя опубликовать; None — можно."""
    active = [o for o in offers if not o.removed]
    if not active:
        return "Удалены все офферы. Верните оффер кнопкой Bring Back или добавьте новый."
    total = sum(o.share for o in active)
    if total == TOTAL_SHARE:
        return None
    if total < TOTAL_SHARE and all(o.pinned for o in active):
        return (
            f"{TOTAL_SHARE - total} % трафика некому отдать: все оставшиеся офферы закреплены. "
            "Снимите закрепление с одного из офферов, верните удалённый или добавьте новый."
        )
    return f"Сумма долей — {total} % вместо 100 %. Снимите закрепление с одного из офферов."


# --- действия редактора ------------------------------------------------------


def add_offer(offers: list[Offer], offer_id: int) -> list[Offer]:
    existing = _find(offers, offer_id, required=False)
    if existing is not None:
        hint = " — верните его кнопкой Bring Back" if existing.removed else ""
        raise ServiceError(f"Оффер #{offer_id} уже есть в потоке{hint}", status_code=409)
    return rebalance([*offers, Offer(offer_id, 0)])


def remove_offer(offers: list[Offer], offer_id: int) -> list[Offer]:
    offer = _find(offers, offer_id)
    if offer.removed:
        raise ServiceError(f"Оффер #{offer_id} уже удалён", status_code=409)
    return rebalance(_put(offers, replace(offer, removed=True)))


def restore_offer(offers: list[Offer], offer_id: int) -> list[Offer]:
    offer = _find(offers, offer_id)
    if not offer.removed:
        raise ServiceError(f"Оффер #{offer_id} не удалён", status_code=409)
    return rebalance(_put(offers, replace(offer, removed=False)))


def pin_offer(offers: list[Offer], offer_id: int, pinned: bool) -> list[Offer]:
    """Закрепление не меняет долей; снятие закрепления запускает пересчёт."""
    offer = _find(offers, offer_id)
    if offer.removed:
        raise ServiceError("Нельзя закрепить долю удалённого оффера", status_code=409)
    updated = _put(offers, replace(offer, pinned=pinned))
    return updated if pinned else rebalance(updated)


def _find(offers: list[Offer], offer_id: int, *, required: bool = True) -> Offer | None:
    for offer in offers:
        if offer.offer_id == offer_id:
            return offer
    if required:
        raise ServiceError(f"Оффера #{offer_id} нет в потоке", status_code=404)
    return None


def _put(offers: list[Offer], updated: Offer) -> list[Offer]:
    return [updated if o.offer_id == updated.offer_id else o for o in offers]
