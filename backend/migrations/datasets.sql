BEGIN;
CREATE TABLE IF NOT EXISTS app.datasets (
    id UUID PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES app.workspaces(id),
    name TEXT NOT NULL,
    checksum TEXT NOT NULL,
    UNIQUE(workspace_id, checksum)
);
CREATE TABLE IF NOT EXISTS app.dataset_revisions (
    id UUID PRIMARY KEY,
    dataset_id UUID NOT NULL REFERENCES app.datasets(id),
    status TEXT NOT NULL CHECK (status IN ('validating','needs_review','publishing','ready','failed')),
    storage_name TEXT NOT NULL,
    suffix TEXT NOT NULL CHECK (suffix IN ('.csv','.xlsx')),
    sheet_name TEXT,
    columns JSONB NOT NULL DEFAULT '[]',
    physical_table TEXT,
    row_count INTEGER,
    timezone TEXT NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
    grain TEXT NOT NULL DEFAULT '',
    data_classification TEXT NOT NULL DEFAULT 'private' CHECK (data_classification IN ('private','synthetic')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS revisions_dataset ON app.dataset_revisions(dataset_id);
CREATE TABLE IF NOT EXISTS app.ingestion_jobs (
    id UUID PRIMARY KEY,
    revision_id UUID NOT NULL UNIQUE REFERENCES app.dataset_revisions(id),
    status TEXT NOT NULL,
    error_code TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
GRANT SELECT, INSERT, UPDATE, DELETE ON app.datasets, app.dataset_revisions, app.ingestion_jobs TO chatsar_app;
INSERT INTO app.schema_migrations(name) VALUES ('datasets') ON CONFLICT DO NOTHING;
COMMIT;
