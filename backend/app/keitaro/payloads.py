"""Сборка тел запросов к Keitaro. Чистые функции — их удобно тестировать."""

import secrets
import string

from app.keitaro.client import JSON

_ALIAS_ALPHABET = string.ascii_lowercase + string.digits


def generate_alias(length: int = 10) -> str:
    """Случайный alias кампании (часть URL: https://domain/<alias>)."""
    return "".join(secrets.choice(_ALIAS_ALPHABET) for _ in range(length))


def campaign_payload(
    *, name: str, alias: str, domain_id: int, group_id: int, traffic_source_id: int
) -> JSON:
    return {
        "name": name,
        "alias": alias,
        "type": "position",  # потоки применяются по порядку
        "state": "active",
        "domain_id": domain_id,
        "group_id": group_id,
        "traffic_source_id": traffic_source_id,
    }


def stream_offers_payload(shares: list[tuple[int, int]], current: list[JSON]) -> list[JSON]:
    """Офферы для PUT /streams/{id} — список целиком заменяет офферы потока.

    shares — пары (offer_id, share). У офферов, которые уже стоят в потоке, сохраняем state.
    """
    states = {int(o["offer_id"]): o.get("state") or "active" for o in current}
    return [
        {"offer_id": offer_id, "share": share, "state": states.get(offer_id, "active")}
        for offer_id, share in shares
    ]
