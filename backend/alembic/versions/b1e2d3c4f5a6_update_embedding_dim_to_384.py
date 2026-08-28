"""update_embedding_dim_to_384

Revision ID: b1e2d3c4f5a6
Revises: adddc61d79b2
Create Date: 2026-08-27 22:53:00.000000

"""
from collections.abc import Sequence

import pgvector.sqlalchemy

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b1e2d3c4f5a6'
down_revision: str | None = 'adddc61d79b2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Alter vector dimension to 384 for HuggingFace embeddings
    op.alter_column(
        'schema_embeddings',
        'embedding',
        existing_type=pgvector.sqlalchemy.vector.VECTOR(dim=1536),
        type_=pgvector.sqlalchemy.vector.VECTOR(dim=384),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Revert vector dimension to 1536
    op.alter_column(
        'schema_embeddings',
        'embedding',
        existing_type=pgvector.sqlalchemy.vector.VECTOR(dim=384),
        type_=pgvector.sqlalchemy.vector.VECTOR(dim=1536),
        existing_nullable=False,
    )
