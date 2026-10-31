-- Chỉ mở miền kiểm tra; quyền thực tế vẫn là grant admin cấp và guard ledger.
BEGIN;
ALTER TABLE app.provider_grants DROP CONSTRAINT provider_grants_max_requests_check;
ALTER TABLE app.provider_grants ADD CONSTRAINT provider_grants_max_requests_check
    CHECK (max_requests BETWEEN 0 AND 500);
ALTER TABLE app.provider_grants DROP CONSTRAINT provider_grants_budget_usd_check;
ALTER TABLE app.provider_grants ADD CONSTRAINT provider_grants_budget_usd_check
    CHECK (budget_usd BETWEEN 0 AND 10);
INSERT INTO app.schema_migrations(name) VALUES ('grant_limits') ON CONFLICT DO NOTHING;
COMMIT;
