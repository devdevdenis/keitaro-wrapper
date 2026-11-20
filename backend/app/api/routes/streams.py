"""Редактор офферов в потоке: правки копятся в черновике и уходят в Keitaro по Push to KT."""

from fastapi import APIRouter

from app.api.deps import KeitaroDep, SessionDep
from app.schemas import StreamEditorOut, StreamOfferAdd, StreamOfferPin
from app.services import stream_editor as editor

router = APIRouter(prefix="/streams/{stream_id}", tags=["stream editor"])


@router.post("/offers", response_model=StreamEditorOut)
async def add_offer(stream_id: int, data: StreamOfferAdd, keitaro: KeitaroDep, session: SessionDep):
    """Add: оффер появляется в списке, доли пересчитываются."""
    state = await editor.add_offer(session, keitaro, stream_id, data.offer_id)
    return editor.editor_view(state)


@router.delete("/offers/{offer_id}", response_model=StreamEditorOut)
async def remove_offer(stream_id: int, offer_id: int, keitaro: KeitaroDep, session: SessionDep):
    """Remove: оффер получает 0 % и остаётся в списке серым."""
    state = await editor.remove_offer(session, keitaro, stream_id, offer_id)
    return editor.editor_view(state)


@router.post("/offers/{offer_id}/restore", response_model=StreamEditorOut)
async def restore_offer(stream_id: int, offer_id: int, keitaro: KeitaroDep, session: SessionDep):
    """Bring Back: оффер снова активен, доли пересчитываются."""
    state = await editor.restore_offer(session, keitaro, stream_id, offer_id)
    return editor.editor_view(state)


@router.put("/offers/{offer_id}/pin", response_model=StreamEditorOut)
async def pin_offer(
    stream_id: int, offer_id: int, data: StreamOfferPin, keitaro: KeitaroDep, session: SessionDep
):
    """Закрепить долю (pinned=true) или снять закрепление (pinned=false)."""
    state = await editor.pin_offer(session, keitaro, stream_id, offer_id, data.pinned)
    return editor.editor_view(state)


@router.post("/push", response_model=StreamEditorOut)
async def push(stream_id: int, keitaro: KeitaroDep, session: SessionDep):
    """Push to KT: публикует черновик в Keitaro."""
    state = await editor.push(session, keitaro, stream_id)
    return editor.editor_view(state)


@router.delete("/draft", response_model=StreamEditorOut)
async def cancel(stream_id: int, keitaro: KeitaroDep, session: SessionDep):
    """Cancel: отбрасывает неопубликованные изменения потока."""
    state = await editor.cancel(session, keitaro, stream_id)
    return editor.editor_view(state)
