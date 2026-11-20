"""campaigns.country_code -> country_codes: GEO is a list of countries

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-20 19:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column("country_codes", postgresql.ARRAY(sa.String(length=2)), nullable=True),
    )
    op.execute("UPDATE campaigns SET country_codes = ARRAY[country_code]")
    op.alter_column("campaigns", "country_codes", nullable=False)
    op.drop_constraint(op.f("fk_campaigns_country_code_countries"), "campaigns", type_="foreignkey")
    op.drop_column("campaigns", "country_code")


def downgrade() -> None:
    # в старой схеме гео — одна страна: оставляем первую из списка
    op.add_column("campaigns", sa.Column("country_code", sa.String(length=2), nullable=True))
    op.execute("UPDATE campaigns SET country_code = country_codes[1]")
    op.alter_column("campaigns", "country_code", nullable=False)
    op.create_foreign_key(
        op.f("fk_campaigns_country_code_countries"),
        "campaigns",
        "countries",
        ["country_code"],
        ["code"],
    )
    op.drop_column("campaigns", "country_codes")
