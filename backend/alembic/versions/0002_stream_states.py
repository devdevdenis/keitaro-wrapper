"""stream_states: offer editor state and drafts

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-20 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stream_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("keitaro_id", sa.Integer(), nullable=False),
        sa.Column("offers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("draft", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("draft_base", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stream_states")),
    )
    op.create_index(
        op.f("ix_stream_states_keitaro_id"), "stream_states", ["keitaro_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_stream_states_keitaro_id"), table_name="stream_states")
    op.drop_table("stream_states")
