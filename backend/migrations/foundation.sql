-- Migration idempotent; chỉ áp dụng bằng role admin/migration của ChatSAR.
BEGIN;
CREATE TABLE IF NOT EXISTS app.schema_migrations (
    name TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO app.schema_migrations(name) VALUES ('foundation') ON CONFLICT DO NOTHING;
GRANT SELECT ON app.schema_migrations TO chatsar_app;
COMMIT;
