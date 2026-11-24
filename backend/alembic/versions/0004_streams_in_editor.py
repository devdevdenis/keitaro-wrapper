"""streams in the editor: templates, stream drafts; campaigns without geo/offer

Campaign creation no longer builds streams from geo and offer: streams are edited in the
campaign editor (both kinds, including new templates not yet in Keitaro).

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-24 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.drop_column("campaigns", "country_codes")
    op.drop_column("campaigns", "offer_id")
    op.drop_column("campaigns", "google_stream_id")
    op.drop_column("campaigns", "offer_stream_id")

    # формат состояния потока поменялся: строки пересоздадутся при следующем открытии
    # редактора (черновики офферов, удалённые офферы и закрепления при этом теряются)
    op.execute("DELETE FROM stream_states")
    op.drop_column("stream_states", "offers")
    op.add_column("stream_states", sa.Column("campaign_id", sa.Integer(), nullable=False))
    op.add_column(
        "stream_states", sa.Column("position", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("stream_states", sa.Column("saved", JSONB, nullable=True))
    op.alter_column("stream_states", "keitaro_id", nullable=True)
    op.create_index(
        op.f("ix_stream_states_campaign_id"), "stream_states", ["campaign_id"], unique=False
    )


def downgrade() -> None:
    op.execute("DELETE FROM stream_states")
    op.drop_index(op.f("ix_stream_states_campaign_id"), table_name="stream_states")
    op.alter_column("stream_states", "keitaro_id", nullable=False)
    op.drop_column("stream_states", "saved")
    op.drop_column("stream_states", "position")
    op.drop_column("stream_states", "campaign_id")
    op.add_column("stream_states", sa.Column("offers", JSONB, nullable=False, server_default="[]"))

    # гео и оффер кампании не восстановить: колонки возвращаются пустыми
    op.add_column("campaigns", sa.Column("offer_stream_id", sa.Integer(), nullable=True))
    op.add_column("campaigns", sa.Column("google_stream_id", sa.Integer(), nullable=True))
    op.add_column("campaigns", sa.Column("offer_id", sa.Integer(), nullable=True))
    op.add_column(
        "campaigns",
        sa.Column("country_codes", postgresql.ARRAY(sa.String(length=2)), nullable=True),
    )
