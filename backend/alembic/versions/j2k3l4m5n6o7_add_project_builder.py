"""Project Builder: link projects to workflows/executions, add project_runs

Revision ID: j2k3l4m5n6o7
Revises: i1j2k3l4m5n6
Create Date: 2026-11-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'j2k3l4m5n6o7'
down_revision = 'i1j2k3l4m5n6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('projects', sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_projects_workflow_id_workflows', 'projects', 'workflows',
                          ['workflow_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_projects_workflow_id', 'projects', ['workflow_id'])

    op.create_table(
        'project_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(30), nullable=False, server_default='running'),
        sa.Column('project_type', sa.String(50), nullable=True),
        sa.Column('current_step', sa.String(255), nullable=True),
        sa.Column('steps', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('repairs', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('warnings', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('error_summary', sa.Text, nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_project_runs_project_id', 'project_runs', ['project_id'])
    op.create_index('ix_project_runs_execution_id', 'project_runs', ['execution_id'])


def downgrade() -> None:
    op.drop_index('ix_project_runs_execution_id', table_name='project_runs')
    op.drop_index('ix_project_runs_project_id', table_name='project_runs')
    op.drop_table('project_runs')
    op.drop_index('ix_projects_workflow_id', table_name='projects')
    op.drop_constraint('fk_projects_workflow_id_workflows', 'projects', type_='foreignkey')
    op.drop_column('projects', 'execution_id')
    op.drop_column('projects', 'workflow_id')
