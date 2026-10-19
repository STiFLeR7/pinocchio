"""policy_externalization

Revision ID: d2a3b4c5e6f7
Revises: c1a2b3c4d5e6
Create Date: 2026-06-22 11:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = 'd2a3b4c5e6f7'
down_revision: str | None = 'c1a2b3c4d5e6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Create system_policies table
    op.create_table('system_policies',
    sa.Column('policy_key', sa.String(length=100), nullable=False),
    sa.Column('policy_value', sqlite.JSON(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('updated_by', sa.String(length=200), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('is_archived', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_system_policies_policy_key'), 'system_policies', ['policy_key'], unique=True)

    # Create system_policy_history table
    op.create_table('system_policy_history',
    sa.Column('policy_key', sa.String(length=100), nullable=False),
    sa.Column('policy_value', sqlite.JSON(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('updated_by', sa.String(length=200), nullable=True),
    sa.Column('change_type', sa.String(length=50), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('is_archived', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_system_policy_history_policy_key'), 'system_policy_history', ['policy_key'], unique=False)

    # Add columns to repository_registry
    op.add_column('repository_registry', sa.Column('concurrency_limit_override', sa.Integer(), nullable=True))
    op.add_column('repository_registry', sa.Column('command_blacklist_additions', sqlite.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade database schema."""
    # Drop columns from repository_registry
    op.drop_column('repository_registry', 'command_blacklist_additions')
    op.drop_column('repository_registry', 'concurrency_limit_override')

    # Drop system_policy_history table
    op.drop_index(op.f('ix_system_policy_history_policy_key'), table_name='system_policy_history')
    op.drop_table('system_policy_history')

    # Drop system_policies table
    op.drop_index(op.f('ix_system_policies_policy_key'), table_name='system_policies')
    op.drop_table('system_policies')
