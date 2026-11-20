"""Сборка тел запросов к Keitaro. Чистые функции — их удобно тестировать."""

import secrets
import string

from app.config import Settings
from app.keitaro.client import JSON

_ALIAS_ALPHABET = string.ascii_lowercase + string.digits


def generate_alias(length: int = 10) -> str:
    """Случайный alias кампании (часть URL: https://domain/<alias>)."""
    return "".join(secrets.choice(_ALIAS_ALPHABET) for _ in range(length))


def campaign_name(raw_name: str, prefix: str) -> str:
    """Добавляет обязательный префикс `test_<фамилия>_`, если его ещё нет."""
    name = raw_name.strip()
    return name if name.startswith(prefix) else f"{prefix}{name}"


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


def google_stream_name(country_codes: list[str], limit: int = 5) -> str:
    """`Google · DE, AT, CH`; длинный список сокращается: `Google · DE, AT, CH, FR, IT +3`."""
    shown = ", ".join(country_codes[:limit])
    rest = len(country_codes) - limit
    return f"Google · {shown}" + (f" +{rest}" if rest > 0 else "")


def google_stream_payload(
    *, campaign_id: int, country_codes: list[str], settings: Settings
) -> JSON:
    """Поток №1: перехватывающий (forced) — всех из выбранных стран отправляет на Google."""
    return {
        "campaign_id": campaign_id,
        "name": google_stream_name(country_codes),
        "type": "forced",
        "schema": "redirect",
        "action_type": settings.stream_redirect_action,
        "action_payload": settings.google_redirect_url,
        "position": 1,
        "state": "active",
        "filter_or": False,
        "filters": [
            {"name": settings.country_filter_name, "mode": "accept", "payload": country_codes}
        ],
    }


def offer_stream_payload(*, campaign_id: int, offer_id: int, settings: Settings) -> JSON:
    """Поток №2: обычный (regular) — отправляет весь остальной трафик на оффер."""
    return {
        "campaign_id": campaign_id,
        "name": "Offer",
        "type": "regular",
        "schema": "landings",
        "action_type": settings.stream_redirect_action,
        "position": 2,
        "state": "active",
        "offers": [{"offer_id": offer_id, "share": 100, "state": "active"}],
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
