-- Thay đổi cộng thêm; không viết lại bảng dữ liệu hoặc metadata đã công bố.
BEGIN;
ALTER TABLE app.dataset_revisions ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '';
ALTER TABLE app.dataset_revisions ADD COLUMN IF NOT EXISTS sharing_providers JSONB NOT NULL DEFAULT '[]';
ALTER TABLE app.dataset_revisions ADD COLUMN IF NOT EXISTS setup_proposal JSONB;
INSERT INTO app.schema_migrations(name) VALUES ('catalog') ON CONFLICT DO NOTHING;
COMMIT;
