"""Редактор потоков кампании (docs/campaign-editor.md).

Все правки потока — название, страны, логика фильтров, редирект, офферы — копятся в черновике
в нашей БД (таблица stream_states) и уходят в Keitaro только по Push to KT. Новые потоки
(шаблоны) живут только у нас, пока их не опубликуют. При каждом открытии редактора потоки
сверяются с Keitaro.
"""

from collections.abc import Callable
from dataclasses import replace

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.keitaro import KeitaroAPI
from app.keitaro.client import JSON
from app.models import Country, StreamState
from app.schemas import EditorOfferOut, StreamOut, StreamPatch
from app.services import offer_shares as rules
from app.services import stream_spec as specs
from app.services.errors import ServiceError
from app.services.offers import ensure_offer_available
from app.services.stream_spec import StreamSpec

CONFLICT_MESSAGE = (
    "Поток изменили в Keitaro, пока здесь были неопубликованные изменения. Нажмите Cancel, "
    "чтобы увидеть актуальное состояние, и повторите свои изменения."
)


# --- чтение --------------------------------------------------------------------


async def sync_campaign(
    session: AsyncSession, campaign_id: int, streams: list[JSON], settings: Settings
) -> list[StreamState]:
    """Сверяет потоки кампании с Keitaro (открытие редактора) и возвращает их по порядку.

    Потоки, удалённые в Keitaro, пропадают и из редактора; шаблоны остаются.
    """
    for stream in streams:
        await _synced_state(session, campaign_id, stream, settings)
    in_keitaro = [s["id"] for s in streams]
    await session.execute(
        delete(StreamState).where(
            StreamState.campaign_id == campaign_id,
            StreamState.keitaro_id.is_not(None),
            StreamState.keitaro_id.not_in(in_keitaro),
        )
    )
    await session.commit()
    return await campaign_streams(session, campaign_id)


async def campaign_streams(session: AsyncSession, campaign_id: int) -> list[StreamState]:
    result = await session.scalars(
        select(StreamState)
        .where(StreamState.campaign_id == campaign_id)
        .order_by(StreamState.position, StreamState.id)
    )
    return list(result)


async def published_countries(session: AsyncSession) -> dict[int, list[str]]:
    """Страны опубликованных перехватывающих потоков по кампаниям — для списка кампаний."""
    by_campaign: dict[int, list[StreamState]] = {}
    for state in await session.scalars(select(StreamState).where(StreamState.saved.is_not(None))):
        by_campaign.setdefault(state.campaign_id, []).append(state)
    return {cid: published_in(states) for cid, states in by_campaign.items()}


def published_in(states: list[StreamState]) -> list[str]:
    """Страны из опубликованных перехватывающих потоков (без черновиков)."""
    codes: list[str] = []
    for state in states:
        spec = specs.load(state.saved)
        if spec is not None and spec.kind == "intercept":
            codes += [c for c in spec.countries if c not in codes]
    return codes


def view(state: StreamState) -> StreamOut:
    saved = specs.load(state.saved)
    draft = specs.load(state.draft)
    shown = draft or saved
    assert shown is not None
    published = (
        {o.offer_id: o.share for o in saved.offers if not o.removed} if saved is not None else {}
    )

    conflict = _has_conflict(state)
    if conflict:
        problem = CONFLICT_MESSAGE
    else:
        problem = specs.publish_problem(draft) if draft is not None else None

    return StreamOut(
        id=state.id,
        keitaro_id=state.keitaro_id,
        kind=shown.kind,
        type=shown.type,
        position=state.position,
        name=shown.name,
        countries=list(shown.countries),
        filter_or=shown.filter_or,
        redirect_url=shown.redirect_url,
        offers=[
            EditorOfferOut(
                offer_id=o.offer_id,
                share=o.share,
                removed=o.removed,
                pinned=o.pinned,
                status="removed" if o.removed else "active" if o.offer_id in published else "new",
                published_share=published.get(o.offer_id),
            )
            for o in shown.offers
        ],
        is_new=state.keitaro_id is None,
        has_draft=draft is not None,
        conflict=conflict,
        problem=problem,
        can_push=draft is not None and problem is None,
    )


# --- потоки: создание и удаление -------------------------------------------------


async def add_templates(
    session: AsyncSession, campaign_id: int, settings: Settings
) -> list[StreamState]:
    """Шаблоны новой кампании: Flow 1 — перехватывающий на Google, Flow 2 — обычный."""
    return [
        await add_stream(session, campaign_id, "intercept", settings),
        await add_stream(session, campaign_id, "regular", settings),
    ]


async def add_stream(
    session: AsyncSession, campaign_id: int, kind: str, settings: Settings
) -> StreamState:
    """Новый поток — шаблон в черновике; в Keitaro он появится по Push to KT."""
    states = await campaign_streams(session, campaign_id)
    names = [(specs.load(s.draft) or specs.load(s.saved)).name for s in states]
    position = max((s.position for s in states), default=0) + 1
    state = StreamState(
        campaign_id=campaign_id,
        position=position,
        draft=specs.template(kind, specs.next_flow_name(names), settings).to_json(),
    )
    session.add(state)
    await session.commit()
    return state


async def delete_stream(session: AsyncSession, keitaro: KeitaroAPI, state_id: int) -> None:
    """Удаляет поток. Опубликованный удаляется и в Keitaro (его можно восстановить там)."""
    state = await _locked_state(session, state_id)
    if state.keitaro_id is not None:
        await keitaro.delete_stream(state.keitaro_id)
    await session.delete(state)
    await session.commit()


# --- правка черновика ----------------------------------------------------------


async def update_fields(
    session: AsyncSession, state_id: int, patch: StreamPatch, settings: Settings
) -> StreamState:
    state = await _locked_state(session, state_id)
    current = specs.load(state.draft) or specs.load(state.saved)
    changes = patch.model_dump(exclude_none=True)
    if current.kind == "other":
        raise ServiceError("Этот поток редактор не меняет")

    kind = changes.pop("kind", current.kind)
    if kind != current.kind and state.keitaro_id is not None:
        raise ServiceError(
            "Тип опубликованного потока не меняется: удалите поток и добавьте новый нужного типа"
        )
    if kind != "intercept" and changes.keys() & {"countries", "filter_or", "redirect_url"}:
        raise ServiceError("Страны, логику фильтров и редирект задают у перехватывающего потока")
    if "countries" in changes:
        await _ensure_countries_known(session, changes["countries"])
        changes["countries"] = tuple(changes["countries"])

    def change(spec: StreamSpec) -> StreamSpec:
        if kind != spec.kind:  # новый поток сменил тип — начинаем с шаблона этого типа
            spec = specs.template(kind, spec.name, settings)
        return replace(spec, **changes)

    return await _apply(session, state, change)


async def add_offer(
    session: AsyncSession, keitaro: KeitaroAPI, state_id: int, offer_id: int
) -> StreamState:
    state = await _offer_state(session, state_id)
    await ensure_offer_available(keitaro, offer_id)
    return await _apply_offers(session, state, lambda offers: rules.add_offer(offers, offer_id))


async def remove_offer(session: AsyncSession, state_id: int, offer_id: int) -> StreamState:
    state = await _offer_state(session, state_id)
    return await _apply_offers(session, state, lambda offers: rules.remove_offer(offers, offer_id))


async def restore_offer(
    session: AsyncSession, keitaro: KeitaroAPI, state_id: int, offer_id: int
) -> StreamState:
    state = await _offer_state(session, state_id)
    saved = specs.load(state.saved)
    in_keitaro = {o.offer_id for o in saved.offers if not o.removed} if saved else set()
    if offer_id not in in_keitaro:
        # оффер вернётся в Keitaro — он мог за это время уйти в архив
        await ensure_offer_available(keitaro, offer_id)
    return await _apply_offers(session, state, lambda offers: rules.restore_offer(offers, offer_id))


async def pin_offer(
    session: AsyncSession, state_id: int, offer_id: int, pinned: bool
) -> StreamState:
    state = await _offer_state(session, state_id)
    return await _apply_offers(
        session, state, lambda offers: rules.pin_offer(offers, offer_id, pinned)
    )


async def cancel(session: AsyncSession, state_id: int) -> StreamState:
    """Отбрасывает черновик. saved уже сверены с Keitaro при последнем открытии/публикации."""
    state = await _locked_state(session, state_id)
    if state.keitaro_id is None:
        raise ServiceError("Поток ещё не создан в Keitaro — отменять нечего, его можно удалить")
    state.draft = None
    state.draft_base = None
    await session.commit()
    return state


# --- публикация ----------------------------------------------------------------


async def push(
    session: AsyncSession, keitaro: KeitaroAPI, state_id: int, settings: Settings
) -> StreamState:
    state = await _locked_state(session, state_id)
    draft = specs.load(state.draft)
    if draft is None:
        raise ServiceError("Нет неопубликованных изменений", status_code=409)
    if problem := specs.publish_problem(draft):
        raise ServiceError(problem, status_code=422)

    if state.keitaro_id is None:  # новый поток
        payload = specs.to_keitaro(draft, None, settings)
        stream = await keitaro.create_stream(
            {**payload, "campaign_id": state.campaign_id, "position": state.position}
        )
        state.keitaro_id = int(stream["id"])
    else:
        current = await keitaro.get_stream(state.keitaro_id)
        state.saved = specs.from_keitaro(current, specs.load(state.saved), settings).to_json()
        if _has_conflict(state):
            await session.commit()  # сохраняем свежее состояние из Keitaro, черновик не трогаем
            raise ServiceError(CONFLICT_MESSAGE, status_code=409)
        stream = await keitaro.update_stream(
            state.keitaro_id, specs.to_keitaro(draft, current, settings)
        )
        if not stream or "id" not in stream:
            stream = await keitaro.get_stream(state.keitaro_id)

    # удалённые офферы остаются в списке серыми, закрепления сохраняются, остальное — из Keitaro
    state.saved = specs.from_keitaro(stream, draft, settings).to_json()
    state.draft = None
    state.draft_base = None
    await session.commit()
    return state


# --- helpers -------------------------------------------------------------------


def _has_conflict(state: StreamState) -> bool:
    """saved отражают Keitaro на момент последней сверки; draft_base — на момент начала правки."""
    if state.draft is None or state.keitaro_id is None:
        return False
    return state.draft_base != specs.signature(specs.load(state.saved))


async def _locked_state(session: AsyncSession, state_id: int) -> StreamState:
    state = await session.scalar(
        select(StreamState)
        .where(StreamState.id == state_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if state is None:
        raise ServiceError("Поток не найден — обновите страницу", status_code=404)
    return state


async def _offer_state(session: AsyncSession, state_id: int) -> StreamState:
    state = await _locked_state(session, state_id)
    if (specs.load(state.draft) or specs.load(state.saved)).kind != "regular":
        raise ServiceError("Офферы есть только у обычного потока")
    return state


async def _synced_state(
    session: AsyncSession, campaign_id: int, stream: JSON, settings: Settings
) -> StreamState:
    """Строка потока, сверенная с Keitaro; создаётся при первом открытии редактора."""
    await session.execute(
        insert(StreamState)
        .values(campaign_id=campaign_id, keitaro_id=stream["id"])
        .on_conflict_do_nothing(index_elements=[StreamState.keitaro_id])
    )
    state = await session.scalar(
        select(StreamState)
        .where(StreamState.keitaro_id == stream["id"])
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    state.campaign_id = campaign_id
    state.position = stream.get("position") or 0
    state.saved = specs.from_keitaro(stream, specs.load(state.saved), settings).to_json()
    return state


async def _apply(
    session: AsyncSession, state: StreamState, change: Callable[[StreamSpec], StreamSpec]
) -> StreamState:
    """Применяет правку к черновику. Если он совпал с Keitaro — черновик не нужен."""
    saved = specs.load(state.saved)
    updated = change(specs.load(state.draft) or saved)
    if updated == saved:
        state.draft = None
        state.draft_base = None
    else:
        if state.draft is None:
            state.draft_base = specs.signature(saved)
        state.draft = updated.to_json()
    await session.commit()
    return state


async def _apply_offers(
    session: AsyncSession,
    state: StreamState,
    change: Callable[[list[rules.Offer]], list[rules.Offer]],
) -> StreamState:
    return await _apply(session, state, lambda spec: spec.with_offers(change(list(spec.offers))))


async def _ensure_countries_known(session: AsyncSession, codes: list[str]) -> None:
    if not codes:
        return
    known = set(await session.scalars(select(Country.code).where(Country.code.in_(codes))))
    unknown = [code for code in codes if code not in known]
    if len(unknown) == 1:
        raise ServiceError(f"Неизвестный код страны: {unknown[0]}", status_code=422)
    if unknown:
        raise ServiceError(f"Неизвестные коды стран: {', '.join(unknown)}", status_code=422)
