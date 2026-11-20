from app.config import Settings
from app.keitaro.client import KeitaroAPI, KeitaroClient
from app.keitaro.exceptions import (
    KeitaroAPIError,
    KeitaroError,
    KeitaroNotConfigured,
    KeitaroUnavailable,
)

__all__ = [
    "KeitaroAPI",
    "KeitaroAPIError",
    "KeitaroClient",
    "KeitaroError",
    "KeitaroNotConfigured",
    "KeitaroUnavailable",
    "build_keitaro_client",
]


def build_keitaro_client(settings: Settings) -> KeitaroAPI | None:
    """Возвращает клиент Keitaro или None, если KEITARO_URL / KEITARO_API_KEY не заданы."""
    if not settings.keitaro_configured:
        return None
    return KeitaroClient(
        settings.keitaro_url, settings.keitaro_api_key, timeout=settings.keitaro_timeout
    )
