"""add_briefings_table

Revision ID: f4c5d6e7f8a9
Revises: e3b4c5d6e7f8
Create Date: 2026-06-22 16:06:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = 'f4c5d6e7f8a9'
down_revision: str | None = 'e3b4c5d6e7f8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.create_table('briefings',
    sa.Column('briefing_type', sa.String(length=100), nullable=False),
    sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('delivery_channels', sqlite.JSON(), nullable=True),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('finding_count', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('is_archived', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_table('briefings')
