from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения. Читаются из переменных окружения и файла backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Keitaro Wrapper"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://keitaro:keitaro@localhost:5432/keitaro_wrapper"
    # отдельная база для pytest; создаётся автоматически, схема пересоздаётся перед каждым тестом
    test_database_url: str = (
        "postgresql+asyncpg://keitaro:keitaro@localhost:5432/keitaro_wrapper_test"
    )
    cors_origins: list[str] = ["http://localhost:5173"]

    # Подключение к трекеру Keitaro
    keitaro_url: str = ""  # например https://tracker.example.com (без /admin_api/v1)
    keitaro_api_key: str = ""
    keitaro_timeout: float = 15.0

    # Правила создания кампаний
    campaign_name_prefix: str = "test_volper_"
    google_redirect_url: str = "https://www.google.com"
    stream_redirect_action: str = "http"  # тип редиректа потока (HTTP 302)
    country_filter_name: str = "country"

    @property
    def keitaro_configured(self) -> bool:
        return bool(self.keitaro_url and self.keitaro_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
