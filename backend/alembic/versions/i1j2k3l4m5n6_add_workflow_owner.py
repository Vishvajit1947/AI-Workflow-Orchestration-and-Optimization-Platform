"""Add workflows.user_id (resource ownership)

Every user-owned resource (stages, executions, context, cache entries, routing
decisions, artifacts) hangs off a workflow, so the owner is recorded once, here.

Existing workflows are NOT assigned to anyone: their creator was never recorded, and
guessing would hand one user's data to another. They keep user_id = NULL, which no
API query matches, so they are hidden rather than exposed. To give them to a known
owner, an operator runs (deliberately, per workflow):

    UPDATE workflows SET user_id = '<user uuid>' WHERE id IN (...);

Idempotent: some databases already have a hand-added workflows.user_id column (with
its own index and foreign key). The upgrade keeps that column and its data and
normalises the index and foreign key to the definitions below.

Revision ID: i1j2k3l4m5n6
Revises: h8i9j0k1l2m3
Create Date: 2026-11-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'i1j2k3l4m5n6'
down_revision = 'h8i9j0k1l2m3'
branch_labels = None
depends_on = None

FK_NAME = 'fk_workflows_user_id_users'
INDEX_NAME = 'ix_workflows_user_id'


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if 'user_id' not in {c['name'] for c in inspector.get_columns('workflows')}:
        op.add_column('workflows', sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True))

    # Replace any other foreign key on the column (e.g. a hand-added ON DELETE SET NULL one)
    for fk in inspector.get_foreign_keys('workflows'):
        if fk['constrained_columns'] == ['user_id'] and fk['name'] != FK_NAME:
            op.drop_constraint(fk['name'], 'workflows', type_='foreignkey')
    if FK_NAME not in {fk['name'] for fk in inspector.get_foreign_keys('workflows')}:
        op.create_foreign_key(FK_NAME, 'workflows', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    if INDEX_NAME not in {ix['name'] for ix in inspector.get_indexes('workflows')}:
        op.create_index(INDEX_NAME, 'workflows', ['user_id'])


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name='workflows')
    op.drop_constraint(FK_NAME, 'workflows', type_='foreignkey')
    op.drop_column('workflows', 'user_id')
