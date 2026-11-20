from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_session
from app.keitaro import KeitaroAPI, KeitaroNotConfigured


def get_keitaro(request: Request) -> KeitaroAPI:
    client: KeitaroAPI | None = getattr(request.app.state, "keitaro", None)
    if client is None:
        raise KeitaroNotConfigured(
            "Keitaro не настроен: задайте KEITARO_URL и KEITARO_API_KEY "
            "(или KEITARO_MOCK=true для работы с заглушкой)"
        )
    return client


SessionDep = Annotated[AsyncSession, Depends(get_session)]
KeitaroDep = Annotated[KeitaroAPI, Depends(get_keitaro)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
