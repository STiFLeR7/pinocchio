"""add_research_findings

Revision ID: e3b4c5d6e7f8
Revises: d2a3b4c5e6f7
Create Date: 2026-06-22 15:52:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = 'e3b4c5d6e7f8'
down_revision: str | None = 'd2a3b4c5e6f7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.create_table('research_findings',
    sa.Column('source', sa.String(length=500), nullable=True),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('url', sa.String(length=1000), nullable=True),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('tags', sqlite.JSON(), nullable=True),
    sa.Column('importance_score', sa.Integer(), nullable=True),
    sa.Column('discovered_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('is_archived', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_table('research_findings')
