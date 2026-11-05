BEGIN;
CREATE TABLE IF NOT EXISTS app.users (
    id UUID PRIMARY KEY,
    provider TEXT NOT NULL CHECK (provider = 'google'),
    provider_subject TEXT NOT NULL,
    display_name TEXT NOT NULL CHECK (length(display_name) BETWEEN 1 AND 200),
    UNIQUE(provider, provider_subject)
);
CREATE TABLE IF NOT EXISTS app.sessions (
    token_hash TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES app.users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    google_nonce_hash TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS sessions_user ON app.sessions(user_id);
CREATE INDEX IF NOT EXISTS sessions_expiry ON app.sessions(expires_at);
CREATE TABLE IF NOT EXISTS app.workspaces (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL REFERENCES app.users(id),
    name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS workspaces_owner ON app.workspaces(owner_id);
GRANT SELECT, INSERT, UPDATE, DELETE ON app.users, app.sessions, app.workspaces TO chatsar_app;
INSERT INTO app.schema_migrations(name) VALUES ('identity') ON CONFLICT DO NOTHING;
COMMIT;
