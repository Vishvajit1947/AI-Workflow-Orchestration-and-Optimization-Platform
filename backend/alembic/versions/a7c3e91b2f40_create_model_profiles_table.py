"""create_model_profiles_table

Revision ID: a7c3e91b2f40
Revises: e431515b2d0f
Create Date: 2026-09-27 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'a7c3e91b2f40'
down_revision: Union[str, None] = 'e431515b2d0f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'model_profiles',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('capabilities', JSONB, server_default='{}', nullable=False),
        sa.Column('max_context_tokens', sa.Integer(), nullable=False),
        sa.Column('max_output_tokens', sa.Integer(), nullable=True),
        sa.Column('cost_per_input_token', sa.Numeric(precision=12, scale=10), nullable=False),
        sa.Column('cost_per_output_token', sa.Numeric(precision=12, scale=10), nullable=False),
        sa.Column('avg_latency_ms', sa.Integer(), nullable=True),
        sa.Column('is_available', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('supports_streaming', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('supports_function_calling', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('strengths', JSONB, server_default='[]', nullable=False),
        sa.Column('limitations', JSONB, server_default='[]', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_model_profiles_provider', 'model_profiles', ['provider'])
    op.create_index('idx_model_profiles_is_available', 'model_profiles', ['is_available'])
    op.create_index('idx_model_profiles_provider_model', 'model_profiles', ['provider', 'model_name'], unique=True)


def downgrade() -> None:
    op.drop_index('idx_model_profiles_provider_model', table_name='model_profiles')
    op.drop_index('idx_model_profiles_is_available', table_name='model_profiles')
    op.drop_index('idx_model_profiles_provider', table_name='model_profiles')
    op.drop_table('model_profiles')
