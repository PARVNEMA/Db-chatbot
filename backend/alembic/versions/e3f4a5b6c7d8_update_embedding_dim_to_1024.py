"""update_embedding_dim_to_1024

Revision ID: e3f4a5b6c7d8
Revises: dbd5fb08f1aa
Create Date: 2026-09-04 16:15:00.000000

"""
from collections.abc import Sequence

import pgvector.sqlalchemy
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e3f4a5b6c7d8'
down_revision: str | None = 'dbd5fb08f1aa'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Clear existing embeddings since dimensions are changing from 768 to 1024
    # and existing vectors cannot be cast across different dimension sizes.
    op.execute("DELETE FROM schema_embeddings")
    op.alter_column(
        'schema_embeddings',
        'embedding',
        existing_type=pgvector.sqlalchemy.vector.VECTOR(dim=768),
        type_=pgvector.sqlalchemy.vector.VECTOR(dim=1024),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Clear existing embeddings on downgrade
    op.execute("DELETE FROM schema_embeddings")
    op.alter_column(
        'schema_embeddings',
        'embedding',
        existing_type=pgvector.sqlalchemy.vector.VECTOR(dim=1024),
        type_=pgvector.sqlalchemy.vector.VECTOR(dim=768),
        existing_nullable=False,
    )
