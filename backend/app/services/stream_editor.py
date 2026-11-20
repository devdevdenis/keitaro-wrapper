"""Редактор офферов в потоках (docs/campaign-editor.md).

Изменения копятся в черновике в нашей БД (таблица stream_states) и уходят в Keitaro только по
Push to KT. При каждом открытии редактора список офферов сверяется с Keitaro.
"""

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.keitaro import KeitaroAPI
from app.keitaro import payloads as p
from app.keitaro.client import JSON
from app.models import StreamState
from app.schemas import EditorOfferOut, EditorStream, StreamEditorOut
from app.services import offer_shares as rules
from app.services.errors import ServiceError
from app.services.offers import ensure_offer_available

OFFER_SCHEMA = "landings"
CONFLICT_MESSAGE = (
    "Поток изменили в Keitaro, пока здесь были неопубликованные изменения. Нажмите Cancel, "
    "чтобы увидеть актуальное состояние, и повторите свои изменения."
)


def has_offers(stream: JSON) -> bool:
    return stream.get("schema") == OFFER_SCHEMA


# --- чтение --------------------------------------------------------------------


async def sync_streams(session: AsyncSession, streams: list[JSON]) -> dict[int, StreamState]:
    """Сверяет потоки с офферами с Keitaro и сохраняет результат (открытие редактора)."""
    states = {s["id"]: await _synced_state(session, s) for s in streams if has_offers(s)}
    await session.commit()
    return states


def editor_stream(stream: JSON, state: StreamState | None) -> EditorStream:
    return EditorStream.model_validate(
        {**stream, "editor": editor_view(state) if state is not None else None}
    )


def editor_view(state: StreamState) -> StreamEditorOut:
    saved = rules.load(state.offers)
    draft = rules.load(state.draft) if state.draft is not None else None
    published = {o.offer_id: o.share for o in saved if not o.removed}

    conflict = _has_conflict(state)
    if conflict:
        problem = CONFLICT_MESSAGE
    else:
        problem = rules.publish_problem(draft) if draft is not None else None

    return StreamEditorOut(
        stream_id=state.keitaro_id,
        offers=[
            EditorOfferOut(
                offer_id=o.offer_id,
                share=o.share,
                removed=o.removed,
                pinned=o.pinned,
                status="removed" if o.removed else "active" if o.offer_id in published else "new",
                published_share=published.get(o.offer_id),
            )
            for o in (draft if draft is not None else saved)
        ],
        has_draft=draft is not None,
        conflict=conflict,
        problem=problem,
        can_push=draft is not None and problem is None,
    )


# --- правка черновика ----------------------------------------------------------


async def add_offer(
    session: AsyncSession, keitaro: KeitaroAPI, stream_id: int, offer_id: int
) -> StreamState:
    state = await _state_for_update(session, keitaro, stream_id)
    await ensure_offer_available(keitaro, offer_id)
    return await _apply(session, state, lambda offers: rules.add_offer(offers, offer_id))


async def remove_offer(
    session: AsyncSession, keitaro: KeitaroAPI, stream_id: int, offer_id: int
) -> StreamState:
    state = await _state_for_update(session, keitaro, stream_id)
    return await _apply(session, state, lambda offers: rules.remove_offer(offers, offer_id))


async def restore_offer(
    session: AsyncSession, keitaro: KeitaroAPI, stream_id: int, offer_id: int
) -> StreamState:
    state = await _state_for_update(session, keitaro, stream_id)
    in_keitaro = {o.offer_id for o in rules.load(state.offers) if not o.removed}
    if offer_id not in in_keitaro:
        # оффер вернётся в Keitaro — он мог за это время уйти в архив
        await ensure_offer_available(keitaro, offer_id)
    return await _apply(session, state, lambda offers: rules.restore_offer(offers, offer_id))


async def pin_offer(
    session: AsyncSession, keitaro: KeitaroAPI, stream_id: int, offer_id: int, pinned: bool
) -> StreamState:
    state = await _state_for_update(session, keitaro, stream_id)
    return await _apply(session, state, lambda offers: rules.pin_offer(offers, offer_id, pinned))


async def cancel(session: AsyncSession, keitaro: KeitaroAPI, stream_id: int) -> StreamState:
    """Отбрасывает черновик. offers уже сверены с Keitaro при последнем открытии/публикации."""
    state = await _state_for_update(session, keitaro, stream_id)
    state.draft = None
    state.draft_base = None
    await session.commit()
    return state


# --- публикация ----------------------------------------------------------------


async def push(session: AsyncSession, keitaro: KeitaroAPI, stream_id: int) -> StreamState:
    state = await _locked_state(session, stream_id)
    if state is None or state.draft is None:
        raise ServiceError("Нет неопубликованных изменений", status_code=409)
    draft = rules.load(state.draft)
    if problem := rules.publish_problem(draft):
        raise ServiceError(problem, status_code=422)

    stream = await keitaro.get_stream(stream_id)
    _ensure_offer_stream(stream)
    state.offers = rules.dump(rules.reconcile(rules.load(state.offers), stream.get("offers", [])))
    if _has_conflict(state):
        await session.commit()  # сохраняем свежее состояние из Keitaro, черновик не трогаем
        raise ServiceError(CONFLICT_MESSAGE, status_code=409)

    shares = [(o.offer_id, o.share) for o in draft if not o.removed]
    updated = await keitaro.update_stream(
        stream_id, {"offers": p.stream_offers_payload(shares, stream.get("offers", []))}
    )
    if "offers" not in (updated or {}):
        updated = await keitaro.get_stream(stream_id)

    # удалённые остаются в списке серыми, закрепления сохраняются, доли — из ответа Keitaro
    state.offers = rules.dump(rules.reconcile(draft, updated["offers"]))
    state.draft = None
    state.draft_base = None
    await session.commit()
    return state


# --- helpers -------------------------------------------------------------------


def _has_conflict(state: StreamState) -> bool:
    """offers отражают Keitaro на момент последней сверки; draft_base — на момент начала правки."""
    return state.draft is not None and state.draft_base != rules.signature(rules.load(state.offers))


def _ensure_offer_stream(stream: JSON) -> None:
    if not has_offers(stream):
        raise ServiceError("Офферы можно менять только в потоке со схемой «landings»")


async def _locked_state(session: AsyncSession, stream_id: int) -> StreamState | None:
    return await session.scalar(
        select(StreamState)
        .where(StreamState.keitaro_id == stream_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def _synced_state(session: AsyncSession, stream: JSON) -> StreamState:
    """Строка состояния потока, сверенная с Keitaro; создаётся при первом обращении."""
    await session.execute(
        insert(StreamState)
        .values(keitaro_id=stream["id"], offers=[])
        .on_conflict_do_nothing(index_elements=[StreamState.keitaro_id])
    )
    state = await _locked_state(session, stream["id"])
    assert state is not None
    state.offers = rules.dump(rules.reconcile(rules.load(state.offers), stream.get("offers", [])))
    return state


async def _state_for_update(
    session: AsyncSession, keitaro: KeitaroAPI, stream_id: int
) -> StreamState:
    state = await _locked_state(session, stream_id)
    if state is None:  # редактор ещё не открывали — берём поток из Keitaro
        stream = await keitaro.get_stream(stream_id)
        _ensure_offer_stream(stream)
        state = await _synced_state(session, stream)
    return state


async def _apply(
    session: AsyncSession,
    state: StreamState,
    change: Callable[[list[rules.Offer]], list[rules.Offer]],
) -> StreamState:
    """Применяет действие к черновику. Если он совпал с Keitaro — черновик не нужен."""
    saved = rules.load(state.offers)
    updated = change(rules.load(state.draft) if state.draft is not None else saved)
    if updated == saved:
        state.draft = None
        state.draft_base = None
    else:
        if state.draft is None:
            state.draft_base = rules.signature(saved)
        state.draft = rules.dump(updated)
    await session.commit()
    return state
