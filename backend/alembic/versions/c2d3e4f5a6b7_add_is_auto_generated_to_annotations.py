"""add_is_auto_generated_to_annotations

Revision ID: c2d3e4f5a6b7
Revises: b1e2d3c4f5a6
Create Date: 2026-08-28 10:33:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5a6b7'
down_revision: str | None = 'b1e2d3c4f5a6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'schema_annotations',
        sa.Column('is_auto_generated', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )


def downgrade() -> None:
    op.drop_column('schema_annotations', 'is_auto_generated')
