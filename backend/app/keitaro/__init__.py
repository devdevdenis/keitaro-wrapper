from app.config import Settings
from app.keitaro.client import KeitaroAPI, KeitaroClient
from app.keitaro.exceptions import (
    KeitaroAPIError,
    KeitaroError,
    KeitaroNotConfigured,
    KeitaroUnavailable,
)
from app.keitaro.fake import FakeKeitaroClient

__all__ = [
    "FakeKeitaroClient",
    "KeitaroAPI",
    "KeitaroAPIError",
    "KeitaroClient",
    "KeitaroError",
    "KeitaroNotConfigured",
    "KeitaroUnavailable",
    "build_keitaro_client",
]


async def build_keitaro_client(settings: Settings) -> KeitaroAPI | None:
    """Возвращает клиент Keitaro, заглушку (KEITARO_MOCK=true) или None, если не настроено."""
    if settings.keitaro_mock:
        from app.fixtures import read_fixture

        fake = FakeKeitaroClient()
        # Заглушка сразу содержит кампании из демо-фикстуры — редактор работает «из коробки»
        await fake.seed_demo(read_fixture("demo_campaigns"), settings)
        return fake
    if not settings.keitaro_configured:
        return None
    return KeitaroClient(
        settings.keitaro_url, settings.keitaro_api_key, timeout=settings.keitaro_timeout
    )
