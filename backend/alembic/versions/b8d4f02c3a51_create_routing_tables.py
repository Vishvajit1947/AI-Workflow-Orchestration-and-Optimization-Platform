"""create_routing_tables

Revision ID: b8d4f02c3a51
Revises: a7c3e91b2f40
Create Date: 2026-09-27 10:05:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'b8d4f02c3a51'
down_revision: Union[str, None] = 'a7c3e91b2f40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'routing_rules',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('stage_type', sa.String(length=100), nullable=False),
        sa.Column('priority_factor', sa.String(length=50), server_default='balanced', nullable=False),
        sa.Column('max_cost_per_call', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('max_latency_ms', sa.Integer(), nullable=True),
        sa.Column('min_capability_score', sa.Numeric(precision=3, scale=2), server_default='0.80', nullable=False),
        sa.Column('preferred_model_id', sa.UUID(), nullable=True),
        sa.Column('fallback_model_id', sa.UUID(), nullable=True),
        sa.Column('config', JSONB, server_default='{}', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['preferred_model_id'], ['model_profiles.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['fallback_model_id'], ['model_profiles.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stage_type'),
    )
    op.create_index('idx_routing_rules_is_active', 'routing_rules', ['is_active'])

    op.create_table(
        'routing_decisions',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('execution_id', sa.UUID(), nullable=False),
        sa.Column('stage_id', sa.UUID(), nullable=False),
        sa.Column('stage_type', sa.String(length=100), nullable=True),
        sa.Column('selected_model_id', sa.UUID(), nullable=True),
        sa.Column('selected_provider', sa.String(length=50), nullable=False),
        sa.Column('selected_model_name', sa.String(length=100), nullable=False),
        sa.Column('selection_reason', sa.String(length=500), nullable=True),
        sa.Column('priority_factor', sa.String(length=50), nullable=True),
        sa.Column('alternatives_considered', JSONB, server_default='[]', nullable=False),
        sa.Column('was_user_override', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('was_fallback', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['stage_id'], ['stages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['selected_model_id'], ['model_profiles.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_routing_decisions_execution_id', 'routing_decisions', ['execution_id'])
    op.create_index('idx_routing_decisions_stage_type', 'routing_decisions', ['stage_type'])


def downgrade() -> None:
    op.drop_index('idx_routing_decisions_stage_type', table_name='routing_decisions')
    op.drop_index('idx_routing_decisions_execution_id', table_name='routing_decisions')
    op.drop_table('routing_decisions')
    op.drop_index('idx_routing_rules_is_active', table_name='routing_rules')
    op.drop_table('routing_rules')
