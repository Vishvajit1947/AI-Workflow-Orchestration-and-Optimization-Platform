"""create_cache_entries_table

Revision ID: e431515b2d0f
Revises: 0bb186599c66
Create Date: 2026-09-26 11:18:33.815081
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'e431515b2d0f'
down_revision: Union[str, None] = '0bb186599c66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'cache_entries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('workflow_id', sa.UUID(), nullable=True),
        sa.Column('stage_id', sa.UUID(), nullable=True),
        sa.Column('stage_type', sa.String(length=100), nullable=True),
        sa.Column('input_text', sa.Text(), nullable=False),
        sa.Column('input_embedding', Vector(1536), nullable=False),
        sa.Column('result', sa.Text(), nullable=False),
        sa.Column('result_tokens', sa.Integer(), nullable=True),
        sa.Column('model_used', sa.String(length=100), nullable=True),
        sa.Column('dependency_hash', sa.String(length=64), nullable=True),
        sa.Column('hit_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('similarity_threshold', sa.Numeric(precision=4, scale=3), server_default='0.92', nullable=False),
        sa.Column('is_valid', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['stage_id'], ['stages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Standard B-tree indexes
    op.create_index('idx_cache_entries_stage_type', 'cache_entries', ['stage_type'])
    op.create_index('idx_cache_entries_is_valid', 'cache_entries', ['is_valid'])
    op.create_index('idx_cache_entries_created_at', 'cache_entries', ['created_at'])

    # IVFFlat vector index for approximate nearest-neighbor cosine similarity search.
    op.execute("""
        CREATE INDEX idx_cache_entries_embedding
        ON cache_entries
        USING ivfflat (input_embedding vector_cosine_ops)
        WITH (lists = 100)
    """)


def downgrade() -> None:
    op.drop_index('idx_cache_entries_embedding', table_name='cache_entries')
    op.drop_index('idx_cache_entries_created_at', table_name='cache_entries')
    op.drop_index('idx_cache_entries_is_valid', table_name='cache_entries')
    op.drop_index('idx_cache_entries_stage_type', table_name='cache_entries')
    op.drop_table('cache_entries')
