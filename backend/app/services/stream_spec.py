"""Поток глазами редактора и правила его публикации (docs/campaign-editor.md).

Чистые функции без обращения к БД и Keitaro. Редактор понимает два вида потоков:

- intercept — перехватывающий (Keitaro: type=forced, schema=redirect): фильтр по странам,
  логика фильтров (ИЛИ/И) и адрес редиректа;
- regular — обычный, с офферами (Keitaro: schema=landings): список офферов и их доли.

Остальные потоки (other) показываются только названием: редактор их не разбирает.
"""

import json
from dataclasses import asdict, dataclass, field, replace
from typing import Literal
from urllib.parse import urlparse

from app.config import Settings
from app.keitaro import payloads as p
from app.keitaro.client import JSON
from app.services import offer_shares as rules
from app.services.offer_shares import Offer

Kind = Literal["intercept", "regular", "other"]

KEITARO_TYPE = {"intercept": "forced", "regular": "regular"}
KEITARO_SCHEMA = {"intercept": "redirect", "regular": "landings"}


@dataclass(frozen=True)
class StreamSpec:
    name: str
    kind: Kind
    type: str | None = None  # тип потока в Keitaro (forced / regular / default) — только чтение
    countries: tuple[str, ...] = ()
    # логика между фильтрами в Keitaro: True — ИЛИ, False — И. В редакторе не меняется:
    # новые потоки создаются с «ИЛИ», у существующих остаётся как в Keitaro
    filter_or: bool = True
    redirect_url: str = ""
    offers: tuple[Offer, ...] = field(default_factory=tuple)

    @classmethod
    def from_json(cls, data: JSON) -> "StreamSpec":
        return cls(
            **{
                **data,
                "countries": tuple(data.get("countries", ())),
                "offers": tuple(rules.load(data.get("offers"))),
            }
        )

    def to_json(self) -> JSON:
        data = asdict(self)
        data["countries"] = list(self.countries)
        data["offers"] = rules.dump(list(self.offers))
        return data

    def with_offers(self, offers: list[Offer]) -> "StreamSpec":
        return replace(self, offers=tuple(offers))


def load(data: JSON | None) -> StreamSpec | None:
    return StreamSpec.from_json(data) if data is not None else None


def kind_of(stream: JSON) -> Kind:
    if stream.get("type") == "forced" and stream.get("schema") == "redirect":
        return "intercept"
    if stream.get("schema") == "landings":
        return "regular"
    return "other"


def template(kind: Kind, name: str, settings: Settings) -> StreamSpec:
    """Шаблон нового потока: перехватывающий — на Google, обычный — без офферов."""
    if kind == "intercept":
        return StreamSpec(
            name=name,
            kind=kind,
            type=KEITARO_TYPE[kind],
            redirect_url=settings.google_redirect_url,
        )
    return StreamSpec(name=name, kind=kind, type=KEITARO_TYPE[kind])


def next_flow_name(names: list[str]) -> str:
    """Flow N, где N — следующий свободный номер: Flow 1, Flow 2, …"""
    taken = set(names)
    number = len(names) + 1
    while f"Flow {number}" in taken:
        number += 1
    return f"Flow {number}"


def from_keitaro(stream: JSON, saved: StreamSpec | None, settings: Settings) -> StreamSpec:
    """Поток из Keitaro в формате редактора.

    Всё берётся из Keitaro; из прошлой сверки сохраняются только удалённые офферы и закрепления.
    """
    kind = kind_of(stream)
    spec = StreamSpec(
        name=stream.get("name") or "",
        kind=kind,
        type=stream.get("type"),
        filter_or=bool(stream.get("filter_or")),
    )
    if kind == "intercept":
        country = _country_filter(stream.get("filters") or [], settings)
        action = stream.get("action_payload")
        spec = replace(
            spec,
            countries=tuple(_filter_values(country["payload"])) if country else (),
            redirect_url=action if isinstance(action, str) else "",
        )
    elif kind == "regular":
        previous = list(saved.offers) if saved is not None else []
        spec = spec.with_offers(rules.reconcile(previous, stream.get("offers") or []))
    return spec


def signature(spec: StreamSpec | None) -> JSON | None:
    """Что реально стоит в Keitaro — для обнаружения правок, сделанных мимо редактора."""
    if spec is None:
        return None
    return {
        "name": spec.name,
        "countries": sorted(spec.countries),
        "filter_or": spec.filter_or,
        "redirect_url": spec.redirect_url,
        "offers": rules.signature(list(spec.offers)),
    }


def publish_problem(spec: StreamSpec) -> str | None:
    """Почему поток нельзя опубликовать; None — можно."""
    if not spec.name.strip():
        return "Укажите название потока."
    if spec.kind == "intercept":
        if not spec.countries:
            return "Выберите хотя бы одну страну — без фильтра поток перехватит весь трафик."
        url = urlparse(spec.redirect_url.strip())
        if url.scheme not in ("http", "https") or not url.netloc:
            return "Укажите адрес редиректа: http://… или https://…"
    if spec.kind == "regular":
        if not spec.offers:
            return "Добавьте хотя бы один оффер."
        return rules.publish_problem(list(spec.offers))
    return None


def to_keitaro(spec: StreamSpec, current: JSON | None, settings: Settings) -> JSON:
    """Тело POST /streams (current=None) или PUT /streams/{id}.

    При обновлении меняются только поля, которыми управляет редактор: остальные фильтры,
    лендинги и настройки потока в Keitaro не трогаем.
    """
    data: JSON = {"name": spec.name.strip()}
    if current is None:
        data.update(
            type=KEITARO_TYPE[spec.kind],
            schema=KEITARO_SCHEMA[spec.kind],
            action_type=settings.stream_redirect_action,
            state="active",
        )
    if spec.kind == "intercept":
        others = [
            {"name": f["name"], "mode": f["mode"], "payload": f.get("payload")}
            for f in (current or {}).get("filters") or []
            if _country_filter([f], settings) is None
        ]
        country = {
            "name": settings.country_filter_name,
            "mode": "accept",
            "payload": list(spec.countries),
        }
        data.update(filters=[*others, country], action_payload=spec.redirect_url.strip())
        if current is None:
            # редактор задаёт только страны — новому потоку ставим логику «ИЛИ»; у существующего
            # логику не трогаем: с другими фильтрами из Keitaro она может быть и «И»
            data["filter_or"] = True
    elif spec.kind == "regular":
        shares = [(o.offer_id, o.share) for o in spec.offers if not o.removed]
        data["offers"] = p.stream_offers_payload(shares, (current or {}).get("offers") or [])
    return data


def _country_filter(filters: list[JSON], settings: Settings) -> JSON | None:
    """Фильтр «страна входит в список» — им управляет редактор."""
    for f in filters:
        if f.get("name") == settings.country_filter_name and f.get("mode", "accept") == "accept":
            return f
    return None


def _filter_values(payload) -> list[str]:
    """Keitaro отдаёт значения фильтра списком, JSON-строкой или строкой через запятую."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            payload = payload.split(",")
    if not isinstance(payload, list):
        payload = [payload]
    return [str(v).strip().upper() for v in payload if str(v).strip()]
