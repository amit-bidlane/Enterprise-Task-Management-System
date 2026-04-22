"""add password hash to users

Revision ID: 20260422_0002
Revises: 20260422_0001
Create Date: 2026-04-22 11:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260422_0002"
down_revision: str | Sequence[str] | None = "20260422_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.execute("UPDATE users SET password_hash = 'pending-reset' WHERE password_hash IS NULL")
    op.alter_column("users", "password_hash", nullable=False)


def downgrade() -> None:
    op.drop_column("users", "password_hash")
