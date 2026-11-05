-- Quota cộng thêm; chỉ admin cấp quyền, runtime chỉ đọc. Không sửa ledger cũ.
BEGIN;
CREATE TABLE IF NOT EXISTS app.provider_grants (
    id UUID PRIMARY KEY,
    provider TEXT NOT NULL CHECK (provider IN ('gemini','knowledge')),
    baseline JSONB NOT NULL,
    max_requests INTEGER NOT NULL CHECK (max_requests BETWEEN 0 AND 100),
    budget_usd NUMERIC NOT NULL CHECK (budget_usd BETWEEN 0 AND 1.50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
GRANT SELECT ON app.provider_grants TO chatsar_app;
ALTER TABLE app.provider_usage ADD COLUMN IF NOT EXISTS grant_id UUID REFERENCES app.provider_grants(id);
ALTER TABLE app.provider_usage ADD COLUMN IF NOT EXISTS dispatch_count INTEGER CHECK (dispatch_count BETWEEN 0 AND 1);
INSERT INTO app.schema_migrations(name) VALUES ('provider_grants') ON CONFLICT DO NOTHING;
COMMIT;
