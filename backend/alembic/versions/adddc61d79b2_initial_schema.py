"""initial_schema

Revision ID: adddc61d79b2
Revises: 
Create Date: 2026-08-24 18:35:11.765672

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'adddc61d79b2'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure pgvector extension exists
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_superuser', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. projects
    op.create_table(
        'projects',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('owner_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(length=1024), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_projects_owner_id'), 'projects', ['owner_id'], unique=False)

    # 3. connections
    op.create_table(
        'connections',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('dialect', sa.String(length=50), nullable=False),
        sa.Column('encrypted_connection_string', sa.String(length=2048), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_connections_project_id'), 'connections', ['project_id'], unique=True)

    # 4. schema_cache
    op.create_table(
        'schema_cache',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('connection_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('introspected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('raw_schema', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['connection_id'], ['connections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_schema_cache_connection_id'), 'schema_cache', ['connection_id'], unique=True)
    op.create_index(op.f('ix_schema_cache_project_id'), 'schema_cache', ['project_id'], unique=False)

    # 5. schema_tables
    op.create_table(
        'schema_tables',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('cache_id', sa.UUID(), nullable=False),
        sa.Column('connection_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('schema_name', sa.String(length=255), nullable=True),
        sa.Column('table_name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['cache_id'], ['schema_cache.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['connection_id'], ['connections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('connection_id', 'schema_name', 'table_name', name='uq_schema_tables_conn_schema_table')
    )
    op.create_index(op.f('ix_schema_tables_cache_id'), 'schema_tables', ['cache_id'], unique=False)
    op.create_index(op.f('ix_schema_tables_connection_id'), 'schema_tables', ['connection_id'], unique=False)
    op.create_index(op.f('ix_schema_tables_project_id'), 'schema_tables', ['project_id'], unique=False)

    # 6. schema_columns
    op.create_table(
        'schema_columns',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('table_id', sa.UUID(), nullable=False),
        sa.Column('connection_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('column_name', sa.String(length=255), nullable=False),
        sa.Column('data_type', sa.String(length=100), nullable=False),
        sa.Column('is_nullable', sa.Boolean(), nullable=False),
        sa.Column('is_primary_key', sa.Boolean(), nullable=False),
        sa.Column('is_foreign_key', sa.Boolean(), nullable=False),
        sa.Column('fk_target_table', sa.String(length=255), nullable=True),
        sa.Column('fk_target_column', sa.String(length=255), nullable=True),
        sa.Column('ordinal_position', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['connection_id'], ['connections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['table_id'], ['schema_tables.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_schema_columns_conn_table', 'schema_columns', ['connection_id', 'table_id'], unique=False)
    op.create_index(op.f('ix_schema_columns_connection_id'), 'schema_columns', ['connection_id'], unique=False)
    op.create_index(op.f('ix_schema_columns_project_id'), 'schema_columns', ['project_id'], unique=False)
    op.create_index(op.f('ix_schema_columns_table_id'), 'schema_columns', ['table_id'], unique=False)

    # 7. schema_annotations
    op.create_table(
        'schema_annotations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('connection_id', sa.UUID(), nullable=False),
        sa.Column('schema_table_id', sa.UUID(), nullable=True),
        sa.Column('schema_column_id', sa.UUID(), nullable=True),
        sa.Column('target_type', sa.String(length=10), nullable=False),
        sa.Column('note', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("(target_type = 'table' AND schema_table_id IS NOT NULL AND schema_column_id IS NULL) OR (target_type = 'column' AND schema_column_id IS NOT NULL AND schema_table_id IS NULL)", name='ck_schema_annotations_target_type'),
        sa.ForeignKeyConstraint(['connection_id'], ['connections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['schema_column_id'], ['schema_columns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['schema_table_id'], ['schema_tables.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_schema_annotations_connection_id'), 'schema_annotations', ['connection_id'], unique=False)
    op.create_index(op.f('ix_schema_annotations_project_id'), 'schema_annotations', ['project_id'], unique=False)
    op.create_index(op.f('ix_schema_annotations_schema_column_id'), 'schema_annotations', ['schema_column_id'], unique=False)
    op.create_index(op.f('ix_schema_annotations_schema_table_id'), 'schema_annotations', ['schema_table_id'], unique=False)

    # 8. schema_embeddings
    op.create_table(
        'schema_embeddings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('schema_column_id', sa.UUID(), nullable=False),
        sa.Column('connection_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1536), nullable=False),
        sa.Column('embed_text', sa.Text(), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['connection_id'], ['connections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['schema_column_id'], ['schema_columns.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_schema_embeddings_connection_id'), 'schema_embeddings', ['connection_id'], unique=False)
    op.create_index(op.f('ix_schema_embeddings_project_id'), 'schema_embeddings', ['project_id'], unique=False)
    op.create_index(op.f('ix_schema_embeddings_schema_column_id'), 'schema_embeddings', ['schema_column_id'], unique=True)

    # 9. chat_sessions
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('connection_id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['connection_id'], ['connections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_sessions_connection_id'), 'chat_sessions', ['connection_id'], unique=False)
    op.create_index('ix_chat_sessions_project_created', 'chat_sessions', ['project_id', sa.literal_column('created_at DESC')], unique=False)
    op.create_index(op.f('ix_chat_sessions_project_id'), 'chat_sessions', ['project_id'], unique=False)

    # 10. chat_messages
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('query_run_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_messages_project_id'), 'chat_messages', ['project_id'], unique=False)
    op.create_index('ix_chat_messages_session_created', 'chat_messages', ['session_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_chat_messages_session_id'), 'chat_messages', ['session_id'], unique=False)

    # 11. query_runs
    op.create_table(
        'query_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('chat_message_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('connection_id', sa.UUID(), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('parent_run_id', sa.UUID(), nullable=True),
        sa.Column('nl_prompt', sa.Text(), nullable=False),
        sa.Column('generated_sql', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('result_summary', sa.Text(), nullable=True),
        sa.Column('result_row_count', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['chat_message_id'], ['chat_messages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['connection_id'], ['connections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_run_id'], ['query_runs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_query_runs_chat_message_id'), 'query_runs', ['chat_message_id'], unique=False)
    op.create_index(op.f('ix_query_runs_connection_id'), 'query_runs', ['connection_id'], unique=False)
    op.create_index(op.f('ix_query_runs_parent_run_id'), 'query_runs', ['parent_run_id'], unique=False)
    op.create_index('ix_query_runs_project_created', 'query_runs', ['project_id', sa.literal_column('created_at DESC')], unique=False)
    op.create_index(op.f('ix_query_runs_project_id'), 'query_runs', ['project_id'], unique=False)
    op.create_index(op.f('ix_query_runs_status'), 'query_runs', ['status'], unique=False)

    # 12. Deferrable FK from chat_messages.query_run_id to query_runs.id
    op.create_foreign_key(
        'fk_chat_messages_query_run_id_query_runs',
        'chat_messages',
        'query_runs',
        ['query_run_id'],
        ['id'],
        ondelete='SET NULL',
        deferrable=True,
        initially='DEFERRED',
    )


def downgrade() -> None:
    # 1. Drop circular FK constraint
    op.drop_constraint('fk_chat_messages_query_run_id_query_runs', 'chat_messages', type_='foreignkey')

    # 2. query_runs
    op.drop_index(op.f('ix_query_runs_status'), table_name='query_runs')
    op.drop_index(op.f('ix_query_runs_project_id'), table_name='query_runs')
    op.drop_index('ix_query_runs_project_created', table_name='query_runs')
    op.drop_index(op.f('ix_query_runs_parent_run_id'), table_name='query_runs')
    op.drop_index(op.f('ix_query_runs_connection_id'), table_name='query_runs')
    op.drop_index(op.f('ix_query_runs_chat_message_id'), table_name='query_runs')
    op.drop_table('query_runs')

    # 3. chat_messages
    op.drop_index(op.f('ix_chat_messages_session_id'), table_name='chat_messages')
    op.drop_index('ix_chat_messages_session_created', table_name='chat_messages')
    op.drop_index(op.f('ix_chat_messages_project_id'), table_name='chat_messages')
    op.drop_table('chat_messages')

    # 4. chat_sessions
    op.drop_index(op.f('ix_chat_sessions_project_id'), table_name='chat_sessions')
    op.drop_index('ix_chat_sessions_project_created', table_name='chat_sessions')
    op.drop_index(op.f('ix_chat_sessions_connection_id'), table_name='chat_sessions')
    op.drop_table('chat_sessions')

    # 5. schema_embeddings
    op.drop_index(op.f('ix_schema_embeddings_schema_column_id'), table_name='schema_embeddings')
    op.drop_index(op.f('ix_schema_embeddings_project_id'), table_name='schema_embeddings')
    op.drop_index(op.f('ix_schema_embeddings_connection_id'), table_name='schema_embeddings')
    op.drop_table('schema_embeddings')

    # 6. schema_annotations
    op.drop_index(op.f('ix_schema_annotations_schema_table_id'), table_name='schema_annotations')
    op.drop_index(op.f('ix_schema_annotations_schema_column_id'), table_name='schema_annotations')
    op.drop_index(op.f('ix_schema_annotations_project_id'), table_name='schema_annotations')
    op.drop_index(op.f('ix_schema_annotations_connection_id'), table_name='schema_annotations')
    op.drop_table('schema_annotations')

    # 7. schema_columns
    op.drop_index(op.f('ix_schema_columns_table_id'), table_name='schema_columns')
    op.drop_index(op.f('ix_schema_columns_project_id'), table_name='schema_columns')
    op.drop_index(op.f('ix_schema_columns_connection_id'), table_name='schema_columns')
    op.drop_index('ix_schema_columns_conn_table', table_name='schema_columns')
    op.drop_table('schema_columns')

    # 8. schema_tables
    op.drop_index(op.f('ix_schema_tables_project_id'), table_name='schema_tables')
    op.drop_index(op.f('ix_schema_tables_connection_id'), table_name='schema_tables')
    op.drop_index(op.f('ix_schema_tables_cache_id'), table_name='schema_tables')
    op.drop_table('schema_tables')

    # 9. schema_cache
    op.drop_index(op.f('ix_schema_cache_project_id'), table_name='schema_cache')
    op.drop_index(op.f('ix_schema_cache_connection_id'), table_name='schema_cache')
    op.drop_table('schema_cache')

    # 10. connections
    op.drop_index(op.f('ix_connections_project_id'), table_name='connections')
    op.drop_table('connections')

    # 11. projects
    op.drop_index(op.f('ix_projects_owner_id'), table_name='projects')
    op.drop_table('projects')

    # 12. users
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
