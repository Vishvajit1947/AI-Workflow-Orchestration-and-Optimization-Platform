"""enable_pgvector_extension

Revision ID: 0bb186599c66
Revises: d24f57e3758d
Create Date: 2026-09-26 10:24:25.498494
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0bb186599c66'
down_revision: Union[str, None] = 'd24f57e3758d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')


def downgrade() -> None:
    # Disable pgvector extension
    op.execute('DROP EXTENSION IF EXISTS vector')
