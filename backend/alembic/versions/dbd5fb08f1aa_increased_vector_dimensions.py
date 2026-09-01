"""increased vector dimensions

Revision ID: dbd5fb08f1aa
Revises: c2d3e4f5a6b7
Create Date: 2026-09-01 15:52:26.592520

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = 'dbd5fb08f1aa'
down_revision: Union[str, None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Clear existing embeddings since dimensions are changing from 384 to 768
    # and existing 384-dim vectors cannot be cast to 768 dimensions.
    op.execute("DELETE FROM schema_embeddings")
    op.alter_column('schema_embeddings', 'embedding',
               existing_type=pgvector.sqlalchemy.vector.VECTOR(dim=384),
               type_=pgvector.sqlalchemy.vector.VECTOR(dim=768),
               existing_nullable=False)


def downgrade() -> None:
    # Clear existing embeddings on downgrade as well
    op.execute("DELETE FROM schema_embeddings")
    op.alter_column('schema_embeddings', 'embedding',
               existing_type=pgvector.sqlalchemy.vector.VECTOR(dim=768),
               type_=pgvector.sqlalchemy.vector.VECTOR(dim=384),
               existing_nullable=False)

