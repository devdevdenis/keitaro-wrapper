from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Country(Base):
    """Справочник стран (ISO 3166-1 alpha-2). Заполняется фикстурами."""

    __tablename__ = "countries"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))


class Campaign(TimestampMixin, Base):
    """Локальная запись о кампании, созданной здесь, а не напрямую в Keitaro."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    keitaro_id: Mapped[int] = mapped_column(unique=True, index=True)
    alias: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    domain_id: Mapped[int]
    group_id: Mapped[int]
    traffic_source_id: Mapped[int]


class StreamState(TimestampMixin, Base):
    """Поток кампании в редакторе (docs/campaign-editor.md).

    keitaro_id — поток в Keitaro; None — новый поток (шаблон), в Keitaro его ещё нет.
    saved — поток, сверенный с Keitaro при последнем открытии редактора (stream_spec.StreamSpec):
    всё из Keitaro плюс удалённые офферы и закрепления, о которых Keitaro не знает.
    draft — неопубликованные изменения в том же формате; None — изменений нет.
    draft_base — что стояло в Keitaro, когда начали правку (stream_spec.signature). Если
    Keitaro с тех пор поменялся, публикация черновика блокируется.
    """

    __tablename__ = "stream_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(index=True)  # кампания в Keitaro
    keitaro_id: Mapped[int | None] = mapped_column(unique=True, index=True)
    position: Mapped[int] = mapped_column(default=0)
    saved: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    draft: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    draft_base: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
