from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- справочники ----------------------------------------------------------


class CountryOut(ORMModel):
    code: str
    name: str


class KeitaroEntity(BaseModel):
    """Минимальное представление сущности Keitaro (домен, группа, источник)."""

    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    state: str | None = None


class OfferOut(KeitaroEntity):
    country: list[str] = Field(default_factory=list)

    @field_validator("country", mode="before")
    @classmethod
    def _country_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        return value if isinstance(value, list) else [value]


# --- кампании -------------------------------------------------------------


def _clean_name(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Название не может быть пустым")
    return value


def normalize_countries(value: list[str]) -> list[str]:
    """Верхний регистр, без дублей, только коды ISO 3166-1 alpha-2."""
    codes = list(dict.fromkeys(code.strip().upper() for code in value))
    bad = [code for code in codes if len(code) != 2 or not code.isalpha()]
    if bad:
        raise ValueError(f"Код страны — две латинские буквы (ISO 3166-1): {', '.join(bad)}")
    return codes


class CampaignIn(BaseModel):
    """Параметры кампании: при создании и при сохранении изменений."""

    name: str = Field(min_length=1, max_length=100, examples=["Nutra DE — Facebook"])
    domain_id: int = Field(gt=0)
    group_id: int = Field(gt=0)
    traffic_source_id: int = Field(gt=0)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return _clean_name(value)


class CampaignRecord(ORMModel):
    """Локальная запись (таблица campaigns)."""

    id: int
    keitaro_id: int
    alias: str
    name: str
    domain_id: int
    group_id: int
    traffic_source_id: int
    created_at: datetime


class CampaignSummary(BaseModel):
    """Кампания из Keitaro; tracked — создана здесь, а не напрямую в Keitaro."""

    model_config = ConfigDict(extra="ignore")

    id: int
    alias: str
    name: str
    state: str | None = None
    group_id: int | None = None
    traffic_source_id: int | None = None
    domain_id: int | None = None
    created_at: str | None = None
    tracked: bool = False
    # страны опубликованных перехватывающих потоков (известны, если кампанию открывали здесь)
    country_codes: list[str] = Field(default_factory=list)


# --- редактор потоков -----------------------------------------------------


class StreamCreate(BaseModel):
    kind: Literal["intercept", "regular"]


class StreamPatch(BaseModel):
    """Правка полей потока в черновике; переданы только изменённые поля."""

    name: str | None = Field(default=None, max_length=100)
    countries: list[str] | None = None
    filter_or: bool | None = None
    redirect_url: str | None = Field(default=None, max_length=2000)

    @field_validator("countries")
    @classmethod
    def _countries(cls, value: list[str] | None) -> list[str] | None:
        return normalize_countries(value) if value is not None else None


class StreamOfferAdd(BaseModel):
    offer_id: int = Field(gt=0)


class StreamOfferPin(BaseModel):
    pinned: bool


class EditorOfferOut(BaseModel):
    offer_id: int
    share: int
    removed: bool
    pinned: bool
    # active — стоит в Keitaro; new — добавлен, но ещё не опубликован; removed — удалён
    status: Literal["active", "new", "removed"]
    # доля в Keitaro; None — в Keitaro этого оффера нет
    published_share: int | None


class StreamOut(BaseModel):
    """Поток в редакторе: черновик, если он есть, иначе состояние из Keitaro."""

    id: int  # поток в нашей БД (у нового потока в Keitaro ещё нет id)
    keitaro_id: int | None
    kind: Literal["intercept", "regular", "other"]
    type: str | None  # тип в Keitaro: forced / regular / default
    position: int
    name: str
    countries: list[str]
    filter_or: bool
    redirect_url: str
    offers: list[EditorOfferOut]
    is_new: bool  # шаблон: в Keitaro потока ещё нет
    has_draft: bool
    conflict: bool  # поток изменили в Keitaro, пока здесь был черновик
    problem: str | None  # почему Push to KT недоступен
    can_push: bool


class CampaignDetail(CampaignSummary):
    streams: list[StreamOut] = Field(default_factory=list)
    record: CampaignRecord | None = None
