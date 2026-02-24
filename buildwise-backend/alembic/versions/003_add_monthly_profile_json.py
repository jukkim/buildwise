"""Add monthly_profile_json column to energy_results.

Revision ID: 003
Revises: 002
Create Date: 2026-02-20

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "energy_results",
        sa.Column("monthly_profile_json", sa.JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("energy_results", "monthly_profile_json")
