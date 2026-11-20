from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    country_code: Mapped[str] = mapped_column(ForeignKey("countries.code"))
    offer_id: Mapped[int]
    domain_id: Mapped[int]
    group_id: Mapped[int]
    traffic_source_id: Mapped[int]
    google_stream_id: Mapped[int | None]
    offer_stream_id: Mapped[int | None]

    country: Mapped[Country] = relationship(lazy="joined")
