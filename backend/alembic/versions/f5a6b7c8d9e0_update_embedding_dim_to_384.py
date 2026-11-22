"""update_embedding_dim_to_384

Revision ID: f5a6b7c8d9e0
Revises: e3f4a5b6c7d8
Create Date: 2026-11-22 21:50:00.000000

"""
from collections.abc import Sequence

import pgvector.sqlalchemy

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5a6b7c8d9e0"
down_revision: str | None = "e3f4a5b6c7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Clear existing embeddings since dimensions are changing from 1024 to 384
    # and existing vectors cannot be cast across different dimension sizes.
    op.execute("DELETE FROM schema_embeddings")
    op.alter_column(
        "schema_embeddings",
        "embedding",
        existing_type=pgvector.sqlalchemy.vector.VECTOR(dim=1024),
        type_=pgvector.sqlalchemy.vector.VECTOR(dim=384),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Clear existing embeddings on downgrade
    op.execute("DELETE FROM schema_embeddings")
    op.alter_column(
        "schema_embeddings",
        "embedding",
        existing_type=pgvector.sqlalchemy.vector.VECTOR(dim=384),
        type_=pgvector.sqlalchemy.vector.VECTOR(dim=1024),
        existing_nullable=False,
    )
