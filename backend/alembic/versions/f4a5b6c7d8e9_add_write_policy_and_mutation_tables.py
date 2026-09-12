"""add_write_policy_and_mutation_tables

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-09-12 18:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4a5b6c7d8e9"
down_revision: str | None = "e3f4a5b6c7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add write policy columns to connections
    op.add_column(
        "connections",
        sa.Column("writes_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "connections",
        sa.Column("max_insert_rows_per_table", sa.Integer(), server_default=sa.text("5"), nullable=False),
    )
    op.add_column(
        "connections",
        sa.Column("max_patch_rows_per_table", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.add_column(
        "connections",
        sa.Column("max_total_rows_per_changeset", sa.Integer(), server_default=sa.text("10"), nullable=False),
    )
    op.add_column(
        "connections",
        sa.Column("max_tables_per_changeset", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.add_column(
        "connections",
        sa.Column("approval_timeout_minutes", sa.Integer(), server_default=sa.text("15"), nullable=False),
    )
    op.add_column(
        "connections",
        sa.Column("undo_window_minutes", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "connections",
        sa.Column("blocked_tables", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # 2. Add constraint metadata to schema_tables
    op.add_column(
        "schema_tables",
        sa.Column("unique_constraints", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "schema_tables",
        sa.Column("check_constraints", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # 3. Add write metadata to schema_columns
    op.add_column(
        "schema_columns",
        sa.Column("column_default", sa.Text(), nullable=True),
    )
    op.add_column(
        "schema_columns",
        sa.Column("is_read_only", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

    # 4. Create pending_mutations table
    op.create_table(
        "pending_mutations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proposer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("approver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="PENDING_APPROVAL", nullable=False),
        sa.Column("change_set_encrypted", sa.Text(), nullable=False),
        sa.Column("change_set_hash", sa.String(length=64), nullable=False),
        sa.Column("preview_row_counts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("total_rows_affected", sa.Integer(), nullable=True),
        sa.Column("execution_result_encrypted", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), unique=True, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pending_mutations_project_id", "pending_mutations", ["project_id"])
    op.create_index("ix_pending_mutations_session_id", "pending_mutations", ["session_id"])
    op.create_index("ix_pending_mutations_connection_id", "pending_mutations", ["connection_id"])
    op.create_index("ix_pending_mutations_status", "pending_mutations", ["status"])
    op.create_index("ix_pending_mutations_session_created", "pending_mutations", ["session_id", sa.text("created_at DESC")])

    # 5. Create mutation_audit_logs table
    op.create_table(
        "mutation_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mutation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pending_mutations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("initiator_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("approver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("operation", sa.String(length=30), nullable=False),
        sa.Column("tables_affected", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("total_rows_affected", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("change_set_hash", sa.String(length=64), nullable=False),
        sa.Column("before_snapshot_encrypted", sa.Text(), nullable=True),
        sa.Column("after_snapshot_encrypted", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error_details", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_mutation_audit_logs_project_id", "mutation_audit_logs", ["project_id"])
    op.create_index("ix_mutation_audit_logs_connection_id", "mutation_audit_logs", ["connection_id"])
    op.create_index("ix_mutation_audit_logs_mutation_id", "mutation_audit_logs", ["mutation_id"])
    op.create_index("ix_mutation_audit_logs_project_created", "mutation_audit_logs", ["project_id", sa.text("created_at DESC")])


def downgrade() -> None:
    # Drop tables
    op.drop_table("mutation_audit_logs")
    op.drop_table("pending_mutations")

    # Drop schema_columns additions
    op.drop_column("schema_columns", "is_read_only")
    op.drop_column("schema_columns", "column_default")

    # Drop schema_tables additions
    op.drop_column("schema_tables", "check_constraints")
    op.drop_column("schema_tables", "unique_constraints")

    # Drop connections write policy additions
    op.drop_column("connections", "blocked_tables")
    op.drop_column("connections", "undo_window_minutes")
    op.drop_column("connections", "approval_timeout_minutes")
    op.drop_column("connections", "max_tables_per_changeset")
    op.drop_column("connections", "max_total_rows_per_changeset")
    op.drop_column("connections", "max_patch_rows_per_table")
    op.drop_column("connections", "max_insert_rows_per_table")
    op.drop_column("connections", "writes_enabled")
