"""add_execution_indexes_and_relationships

Revision ID: d24f57e3758d
Revises: f9282f3834c7
Create Date: 2026-09-25 21:34:59.876132
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd24f57e3758d'
down_revision: Union[str, None] = 'f9282f3834c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make stage_id nullable (it may not exist for workflow-level execution records)
    op.alter_column('execution_records', 'stage_id',
                    existing_type=sa.UUID(),
                    nullable=True)
    
    # Add indexes for better query performance
    op.create_index('idx_execution_records_execution_id', 'execution_records', ['execution_id'])
    op.create_index('idx_execution_records_workflow_id', 'execution_records', ['workflow_id'])
    op.create_index('idx_execution_records_status', 'execution_records', ['status'])
    op.create_index('idx_execution_records_created_at', 'execution_records', ['created_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_execution_records_created_at', table_name='execution_records')
    op.drop_index('idx_execution_records_status', table_name='execution_records')
    op.drop_index('idx_execution_records_workflow_id', table_name='execution_records')
    op.drop_index('idx_execution_records_execution_id', table_name='execution_records')
    
    # Revert stage_id to NOT NULL
    op.alter_column('execution_records', 'stage_id',
                    existing_type=sa.UUID(),
                    nullable=False)
