from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
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
    """Локальная запись о кампании, созданной через обёртку."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    keitaro_id: Mapped[int] = mapped_column(unique=True, index=True)
    alias: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    # гео: одна или несколько стран (коды из справочника countries), трафик из них — на Google
    country_codes: Mapped[list[str]] = mapped_column(ARRAY(String(2)))
    offer_id: Mapped[int]
    domain_id: Mapped[int]
    group_id: Mapped[int]
    traffic_source_id: Mapped[int]
    google_stream_id: Mapped[int | None]
    offer_stream_id: Mapped[int | None]


class StreamState(TimestampMixin, Base):
    """Состояние редактора офферов для потока Keitaro со схемой «landings».

    offers — список офферов, сверенный с Keitaro при последнем открытии редактора: доли из
    Keitaro, плюс удалённые офферы и закрепления, о которых Keitaro не знает.
    draft — неопубликованные изменения (тот же формат); None — изменений нет.
    draft_base — что стояло в Keitaro, когда начали правку (offer_shares.signature). Если
    Keitaro с тех пор поменялся, публикация черновика блокируется.
    """

    __tablename__ = "stream_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    keitaro_id: Mapped[int] = mapped_column(unique=True, index=True)
    offers: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    draft: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    draft_base: Mapped[list[list[int]] | None] = mapped_column(JSONB)
