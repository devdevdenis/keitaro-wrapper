"""Редактор потока: правки копятся в черновике и уходят в Keitaro по Push to KT.

{stream_id} — id потока в нашей БД (у нового потока в Keitaro id ещё нет).
"""

from fastapi import APIRouter, status

from app.api.deps import KeitaroDep, SessionDep, SettingsDep
from app.schemas import StreamOfferAdd, StreamOfferPin, StreamOut, StreamPatch
from app.services import stream_editor as editor

router = APIRouter(prefix="/streams/{stream_id}", tags=["stream editor"])


@router.patch("", response_model=StreamOut)
async def update_stream(stream_id: int, data: StreamPatch, session: SessionDep):
    """Название, страны, логика фильтров (ИЛИ/И), адрес редиректа — в черновик."""
    return editor.view(await editor.update_fields(session, stream_id, data))


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stream(stream_id: int, keitaro: KeitaroDep, session: SessionDep) -> None:
    """Удалить поток: опубликованный — и в Keitaro, шаблон — только здесь."""
    await editor.delete_stream(session, keitaro, stream_id)


@router.post("/offers", response_model=StreamOut)
async def add_offer(stream_id: int, data: StreamOfferAdd, keitaro: KeitaroDep, session: SessionDep):
    """Add: оффер появляется в списке, доли пересчитываются."""
    return editor.view(await editor.add_offer(session, keitaro, stream_id, data.offer_id))


@router.delete("/offers/{offer_id}", response_model=StreamOut)
async def remove_offer(stream_id: int, offer_id: int, session: SessionDep):
    """Remove: оффер получает 0 % и остаётся в списке серым."""
    return editor.view(await editor.remove_offer(session, stream_id, offer_id))


@router.post("/offers/{offer_id}/restore", response_model=StreamOut)
async def restore_offer(stream_id: int, offer_id: int, keitaro: KeitaroDep, session: SessionDep):
    """Bring Back: оффер снова активен, доли пересчитываются."""
    return editor.view(await editor.restore_offer(session, keitaro, stream_id, offer_id))


@router.put("/offers/{offer_id}/pin", response_model=StreamOut)
async def pin_offer(stream_id: int, offer_id: int, data: StreamOfferPin, session: SessionDep):
    """Закрепить долю (pinned=true) или снять закрепление (pinned=false)."""
    return editor.view(await editor.pin_offer(session, stream_id, offer_id, data.pinned))


@router.post("/push", response_model=StreamOut)
async def push(stream_id: int, keitaro: KeitaroDep, session: SessionDep, settings: SettingsDep):
    """Push to KT: создаёт поток в Keitaro или публикует его черновик."""
    return editor.view(await editor.push(session, keitaro, stream_id, settings))


@router.delete("/draft", response_model=StreamOut)
async def cancel(stream_id: int, session: SessionDep):
    """Cancel: отбрасывает неопубликованные изменения потока."""
    return editor.view(await editor.cancel(session, stream_id))
