"""governance_semaphores

Revision ID: c1a2b3c4d5e6
Revises: bb6af9e30a24
Create Date: 2026-06-22 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c1a2b3c4d5e6'
down_revision: str | None = 'bb6af9e30a24'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.create_table('governance_semaphores',
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('is_locked', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('is_archived', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_governance_semaphores_name'), 'governance_semaphores', ['name'], unique=True)


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_index(op.f('ix_governance_semaphores_name'), table_name='governance_semaphores')
    op.drop_table('governance_semaphores')
