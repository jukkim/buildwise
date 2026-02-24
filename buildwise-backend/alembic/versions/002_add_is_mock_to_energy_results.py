"""Add is_mock column to energy_results.

Revision ID: 002
Revises: 001
Create Date: 2026-02-19

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "energy_results",
        sa.Column("is_mock", sa.Boolean, nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("energy_results", "is_mock")
