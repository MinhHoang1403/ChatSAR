BEGIN;
CREATE TABLE IF NOT EXISTS app.conversations (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES app.workspaces(id),
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS conversations_workspace ON app.conversations(workspace_id);
CREATE TABLE IF NOT EXISTS app.messages (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES app.conversations(id),
    revision_id UUID NOT NULL REFERENCES app.dataset_revisions(id),
    question TEXT NOT NULL,
    request_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    provider TEXT NOT NULL,
    status TEXT NOT NULL,
    envelope JSONB,
    query_plan JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(conversation_id, request_key)
);
CREATE TABLE IF NOT EXISTS app.result_records (
    id UUID PRIMARY KEY,
    message_id UUID NOT NULL UNIQUE REFERENCES app.messages(id),
    envelope JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS app.provider_usage (
    id UUID PRIMARY KEY,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    status TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    thought_tokens INTEGER,
    estimated_cost_usd NUMERIC,
    reserved_cost_usd NUMERIC NOT NULL DEFAULT 0,
    latency_ms DOUBLE PRECISION,
    error_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
GRANT SELECT,INSERT,UPDATE,DELETE ON app.conversations,app.messages,app.result_records,app.provider_usage TO chatsar_app;
INSERT INTO app.schema_migrations(name) VALUES ('conversation') ON CONFLICT DO NOTHING;
COMMIT;
