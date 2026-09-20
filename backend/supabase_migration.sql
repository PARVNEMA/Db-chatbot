BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> adddc61d79b2

CREATE EXTENSION IF NOT EXISTS vector;;

CREATE TABLE users (
    id UUID NOT NULL, 
    email VARCHAR(255) NOT NULL, 
    hashed_password VARCHAR(255) NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    is_superuser BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE projects (
    id UUID NOT NULL, 
    owner_id UUID NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    description VARCHAR(1024), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_projects_owner_id ON projects (owner_id);

CREATE TABLE connections (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    dialect VARCHAR(50) NOT NULL, 
    encrypted_connection_string VARCHAR(2048) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX ix_connections_project_id ON connections (project_id);

CREATE TABLE schema_cache (
    id UUID NOT NULL, 
    connection_id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    introspected_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    raw_schema JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(connection_id) REFERENCES connections (id) ON DELETE CASCADE, 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX ix_schema_cache_connection_id ON schema_cache (connection_id);

CREATE INDEX ix_schema_cache_project_id ON schema_cache (project_id);

CREATE TABLE schema_tables (
    id UUID NOT NULL, 
    cache_id UUID NOT NULL, 
    connection_id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    schema_name VARCHAR(255), 
    table_name VARCHAR(255) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(cache_id) REFERENCES schema_cache (id) ON DELETE CASCADE, 
    FOREIGN KEY(connection_id) REFERENCES connections (id) ON DELETE CASCADE, 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
    CONSTRAINT uq_schema_tables_conn_schema_table UNIQUE (connection_id, schema_name, table_name)
);

CREATE INDEX ix_schema_tables_cache_id ON schema_tables (cache_id);

CREATE INDEX ix_schema_tables_connection_id ON schema_tables (connection_id);

CREATE INDEX ix_schema_tables_project_id ON schema_tables (project_id);

CREATE TABLE schema_columns (
    id UUID NOT NULL, 
    table_id UUID NOT NULL, 
    connection_id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    column_name VARCHAR(255) NOT NULL, 
    data_type VARCHAR(100) NOT NULL, 
    is_nullable BOOLEAN NOT NULL, 
    is_primary_key BOOLEAN NOT NULL, 
    is_foreign_key BOOLEAN NOT NULL, 
    fk_target_table VARCHAR(255), 
    fk_target_column VARCHAR(255), 
    ordinal_position INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(connection_id) REFERENCES connections (id) ON DELETE CASCADE, 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
    FOREIGN KEY(table_id) REFERENCES schema_tables (id) ON DELETE CASCADE
);

CREATE INDEX ix_schema_columns_conn_table ON schema_columns (connection_id, table_id);

CREATE INDEX ix_schema_columns_connection_id ON schema_columns (connection_id);

CREATE INDEX ix_schema_columns_project_id ON schema_columns (project_id);

CREATE INDEX ix_schema_columns_table_id ON schema_columns (table_id);

CREATE TABLE schema_annotations (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    connection_id UUID NOT NULL, 
    schema_table_id UUID, 
    schema_column_id UUID, 
    target_type VARCHAR(10) NOT NULL, 
    note TEXT NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_schema_annotations_target_type CHECK ((target_type = 'table' AND schema_table_id IS NOT NULL AND schema_column_id IS NULL) OR (target_type = 'column' AND schema_column_id IS NOT NULL AND schema_table_id IS NULL)), 
    FOREIGN KEY(connection_id) REFERENCES connections (id) ON DELETE CASCADE, 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
    FOREIGN KEY(schema_column_id) REFERENCES schema_columns (id) ON DELETE CASCADE, 
    FOREIGN KEY(schema_table_id) REFERENCES schema_tables (id) ON DELETE CASCADE
);

CREATE INDEX ix_schema_annotations_connection_id ON schema_annotations (connection_id);

CREATE INDEX ix_schema_annotations_project_id ON schema_annotations (project_id);

CREATE INDEX ix_schema_annotations_schema_column_id ON schema_annotations (schema_column_id);

CREATE INDEX ix_schema_annotations_schema_table_id ON schema_annotations (schema_table_id);

CREATE TABLE schema_embeddings (
    id UUID NOT NULL, 
    schema_column_id UUID NOT NULL, 
    connection_id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    embedding VECTOR(1536) NOT NULL, 
    embed_text TEXT NOT NULL, 
    model VARCHAR(100) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(connection_id) REFERENCES connections (id) ON DELETE CASCADE, 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
    FOREIGN KEY(schema_column_id) REFERENCES schema_columns (id) ON DELETE CASCADE
);

CREATE INDEX ix_schema_embeddings_connection_id ON schema_embeddings (connection_id);

CREATE INDEX ix_schema_embeddings_project_id ON schema_embeddings (project_id);

CREATE UNIQUE INDEX ix_schema_embeddings_schema_column_id ON schema_embeddings (schema_column_id);

CREATE TABLE chat_sessions (
    id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    connection_id UUID NOT NULL, 
    title VARCHAR(500), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(connection_id) REFERENCES connections (id) ON DELETE CASCADE, 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE INDEX ix_chat_sessions_connection_id ON chat_sessions (connection_id);

CREATE INDEX ix_chat_sessions_project_created ON chat_sessions (project_id, created_at DESC);

CREATE INDEX ix_chat_sessions_project_id ON chat_sessions (project_id);

CREATE TABLE chat_messages (
    id UUID NOT NULL, 
    session_id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    role VARCHAR(20) NOT NULL, 
    content TEXT NOT NULL, 
    token_count INTEGER, 
    metadata JSONB, 
    query_run_id UUID, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE, 
    FOREIGN KEY(session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE
);

CREATE INDEX ix_chat_messages_project_id ON chat_messages (project_id);

CREATE INDEX ix_chat_messages_session_created ON chat_messages (session_id, created_at);

CREATE INDEX ix_chat_messages_session_id ON chat_messages (session_id);

CREATE TABLE query_runs (
    id UUID NOT NULL, 
    chat_message_id UUID NOT NULL, 
    project_id UUID NOT NULL, 
    connection_id UUID NOT NULL, 
    attempt_number INTEGER NOT NULL, 
    parent_run_id UUID, 
    nl_prompt TEXT NOT NULL, 
    generated_sql TEXT, 
    status VARCHAR(30) NOT NULL, 
    error_message TEXT, 
    result_summary TEXT, 
    result_row_count INTEGER, 
    latency_ms INTEGER, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(chat_message_id) REFERENCES chat_messages (id) ON DELETE CASCADE, 
    FOREIGN KEY(connection_id) REFERENCES connections (id) ON DELETE CASCADE, 
    FOREIGN KEY(parent_run_id) REFERENCES query_runs (id) ON DELETE SET NULL, 
    FOREIGN KEY(project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE INDEX ix_query_runs_chat_message_id ON query_runs (chat_message_id);

CREATE INDEX ix_query_runs_connection_id ON query_runs (connection_id);

CREATE INDEX ix_query_runs_parent_run_id ON query_runs (parent_run_id);

CREATE INDEX ix_query_runs_project_created ON query_runs (project_id, created_at DESC);

CREATE INDEX ix_query_runs_project_id ON query_runs (project_id);

CREATE INDEX ix_query_runs_status ON query_runs (status);

ALTER TABLE chat_messages ADD CONSTRAINT fk_chat_messages_query_run_id_query_runs FOREIGN KEY(query_run_id) REFERENCES query_runs (id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;

INSERT INTO alembic_version (version_num) VALUES ('adddc61d79b2') RETURNING alembic_version.version_num;

-- Running upgrade adddc61d79b2 -> b1e2d3c4f5a6

ALTER TABLE schema_embeddings ALTER COLUMN embedding TYPE VECTOR(384);

UPDATE alembic_version SET version_num='b1e2d3c4f5a6' WHERE alembic_version.version_num = 'adddc61d79b2';

-- Running upgrade b1e2d3c4f5a6 -> c2d3e4f5a6b7

ALTER TABLE schema_annotations ADD COLUMN is_auto_generated BOOLEAN DEFAULT false NOT NULL;

UPDATE alembic_version SET version_num='c2d3e4f5a6b7' WHERE alembic_version.version_num = 'b1e2d3c4f5a6';

-- Running upgrade c2d3e4f5a6b7 -> dbd5fb08f1aa

DELETE FROM schema_embeddings;

ALTER TABLE schema_embeddings ALTER COLUMN embedding TYPE VECTOR(768);

UPDATE alembic_version SET version_num='dbd5fb08f1aa' WHERE alembic_version.version_num = 'c2d3e4f5a6b7';

-- Running upgrade dbd5fb08f1aa -> e3f4a5b6c7d8

DELETE FROM schema_embeddings;

ALTER TABLE schema_embeddings ALTER COLUMN embedding TYPE VECTOR(1024);

UPDATE alembic_version SET version_num='e3f4a5b6c7d8' WHERE alembic_version.version_num = 'dbd5fb08f1aa';

COMMIT;

