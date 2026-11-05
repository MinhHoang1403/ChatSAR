-- Giữ ledger gốc; chỉ admin duyệt dự phòng theo từng lượt, app không tự mở guard.
BEGIN;
ALTER TABLE app.provider_usage ADD COLUMN IF NOT EXISTS http_status INTEGER
    CHECK (http_status BETWEEN 100 AND 599);
CREATE TABLE IF NOT EXISTS app.provider_usage_reviews (
    usage_id UUID PRIMARY KEY REFERENCES app.provider_usage(id),
    policy TEXT NOT NULL CHECK (policy = 'retain_full_reserve'),
    accounted_reserve_usd NUMERIC NOT NULL CHECK (accounted_reserve_usd > 0),
    usage_snapshot JSONB NOT NULL,
    evidence JSONB NOT NULL,
    authority TEXT NOT NULL CHECK (length(authority) BETWEEN 10 AND 1000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
GRANT SELECT ON app.provider_usage_reviews TO chatsar_app;
CREATE TABLE IF NOT EXISTS app.dataset_sharing_events (
    id UUID PRIMARY KEY,
    revision_id UUID NOT NULL REFERENCES app.dataset_revisions(id) ON DELETE CASCADE,
    owner_id UUID NOT NULL REFERENCES app.users(id),
    previous_providers JSONB NOT NULL,
    sharing_providers JSONB NOT NULL,
    request_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
GRANT SELECT, INSERT ON app.dataset_sharing_events TO chatsar_app;
INSERT INTO app.schema_migrations(name) VALUES ('usage_review') ON CONFLICT DO NOTHING;
COMMIT;
