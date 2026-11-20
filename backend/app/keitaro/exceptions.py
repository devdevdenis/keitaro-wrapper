from typing import Any


class KeitaroError(Exception):
    """Базовая ошибка при работе с Keitaro."""

    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


class KeitaroNotConfigured(KeitaroError):
    """Не заданы KEITARO_URL / KEITARO_API_KEY."""


class KeitaroUnavailable(KeitaroError):
    """Трекер недоступен (сеть, таймаут)."""


class KeitaroAPIError(KeitaroError):
    """Трекер ответил ошибкой (4xx/5xx)."""
