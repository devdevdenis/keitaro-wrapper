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


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["campaign1"])
    country_codes: list[str] = Field(min_length=1, examples=[["DE", "AT"]])
    offer_id: int = Field(gt=0)
    domain_id: int = Field(gt=0)
    group_id: int = Field(gt=0)
    traffic_source_id: int = Field(gt=0)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Название не может быть пустым")
        return value

    @field_validator("country_codes")
    @classmethod
    def _normalize_countries(cls, value: list[str]) -> list[str]:
        codes = list(dict.fromkeys(code.strip().upper() for code in value))  # без дублей
        bad = [code for code in codes if len(code) != 2 or not code.isalpha()]
        if bad:
            raise ValueError(f"Код страны — две латинские буквы (ISO 3166-1): {', '.join(bad)}")
        return codes


class CampaignRecord(ORMModel):
    """Локальная запись (таблица campaigns)."""

    id: int
    keitaro_id: int
    alias: str
    name: str
    country_codes: list[str]
    offer_id: int
    domain_id: int
    group_id: int
    traffic_source_id: int
    google_stream_id: int | None
    offer_stream_id: int | None
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
    created_at: str | None = None
    tracked: bool = False
    country_codes: list[str] = Field(default_factory=list)
    domain_id: int | None = None


class StreamFilter(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    name: str
    mode: str
    payload: Any = None


class StreamOffer(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    offer_id: int
    share: int
    state: str | None = None


class StreamOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    campaign_id: int
    name: str | None = None
    type: str
    schema_: str | None = Field(default=None, alias="schema", serialization_alias="schema")
    action_type: str | None = None
    action_payload: Any = None
    position: int | None = None
    state: str | None = None
    filters: list[StreamFilter] = Field(default_factory=list)
    offers: list[StreamOffer] = Field(default_factory=list)


class CampaignCreated(BaseModel):
    record: CampaignRecord
    streams: list[StreamOut]


# --- редактор офферов -----------------------------------------------------


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


class StreamEditorOut(BaseModel):
    """Офферы потока глазами редактора: черновик, если он есть, иначе состояние из Keitaro."""

    stream_id: int
    offers: list[EditorOfferOut]
    has_draft: bool
    conflict: bool  # поток изменили в Keitaro, пока здесь был черновик
    problem: str | None  # почему Push to KT недоступен
    can_push: bool


class EditorStream(BaseModel):
    """Поток кампании в редакторе. editor = None — поток без офферов, редактор его не разбирает."""

    model_config = ConfigDict(extra="ignore")

    id: int
    name: str | None = None
    type: str
    schema_: str | None = Field(default=None, alias="schema", serialization_alias="schema")
    position: int | None = None
    state: str | None = None
    editor: StreamEditorOut | None = None


class CampaignDetail(CampaignSummary):
    streams: list[EditorStream] = Field(default_factory=list)
    record: CampaignRecord | None = None
