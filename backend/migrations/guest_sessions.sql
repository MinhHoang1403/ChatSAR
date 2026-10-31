-- Principal khách có scope riêng; không nhận dạng khách thành tài khoản Google.
BEGIN;
ALTER TABLE app.users DROP CONSTRAINT IF EXISTS users_provider_check;
ALTER TABLE app.users ADD CONSTRAINT users_provider_check CHECK (provider IN ('google','guest'));
INSERT INTO app.schema_migrations(name) VALUES ('guest_sessions') ON CONFLICT DO NOTHING;
COMMIT;
