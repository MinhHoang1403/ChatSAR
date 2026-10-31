BEGIN;
ALTER TABLE app.users ADD COLUMN IF NOT EXISTS phone TEXT NOT NULL DEFAULT ''
    CHECK (length(phone) <= 40);
ALTER TABLE app.users ADD COLUMN IF NOT EXISTS interests TEXT NOT NULL DEFAULT ''
    CHECK (length(interests) <= 1000);
ALTER TABLE app.conversations ADD COLUMN IF NOT EXISTS revision_id UUID
    REFERENCES app.dataset_revisions(id);
-- Chỉ backfill lịch sử có duy nhất một nguồn; trường hợp cũ mơ hồ giữ NULL.
UPDATE app.conversations c SET revision_id = source.revision_id
FROM (
    SELECT conversation_id, (array_agg(DISTINCT revision_id))[1] AS revision_id
    FROM app.messages GROUP BY conversation_id HAVING count(DISTINCT revision_id) = 1
) source
WHERE c.id = source.conversation_id AND c.revision_id IS NULL;
INSERT INTO app.schema_migrations(name) VALUES ('chat_management') ON CONFLICT DO NOTHING;
COMMIT;
