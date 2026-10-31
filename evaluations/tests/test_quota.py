"""Quota trên PostgreSQL thật, test rows riêng; không gọi mạng model."""

import os
import unittest
from uuid import uuid4

from evaluations.oracle import postgres
from evaluations.persistence import inside


@unittest.skipUnless(os.getenv("CHATSAR_POSTGRES_TESTS") == "1", "Cần PostgreSQL thật")
class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.grant = str(uuid4())
        postgres(
            "INSERT INTO app.provider_grants(id,provider,baseline,max_requests,budget_usd) "
            f"VALUES ('{self.grant}','gemini','{{}}',2,0.03);"
        )

    def tearDown(self):
        # Chỉ test reservations thuộc grant UUID do setUp này tạo; không xóa ledger cũ.
        postgres(
            f"DELETE FROM app.provider_usage_reviews WHERE usage_id IN (SELECT id FROM app.provider_usage WHERE grant_id='{self.grant}');"
            f"DELETE FROM app.provider_usage WHERE grant_id='{self.grant}';"
            f"DELETE FROM app.provider_grants WHERE id='{self.grant}';"
        )

    def run_quota(self, code):
        output = inside(
            """
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from unittest.mock import patch
from app import providers
from app.config import Settings
from app.database import get_engine
from app.errors import AppError
from app.schema import provider_usage
from sqlalchemy import select,func
settings=Settings(cloud_calls_allowed=True,cloud_max_requests=1000,
    gemini_max_requests=1000,knowledge_max_requests=0,cloud_budget_usd=100,
    cloud_grant_id='""" + self.grant + """')
def reserve(amount='0.01'):
    try:
        return str(providers.reserve_call('gemini','gemini-3.5-flash-lite',Decimal(amount)))
    except AppError as error:
        return error.code
with patch.object(providers,'get_settings',return_value=settings):
""" + "\n".join("    " + line for line in code.splitlines()) + """
get_engine().dispose()
print('PASS')
"""
        )
        self.assertEqual(output.strip(), "PASS")

    def test_concurrent_reservations_stop_at_limit_and_provider_is_separate(self):
        self.run_quota("""with ThreadPoolExecutor(max_workers=4) as executor:
    outcomes=list(executor.map(lambda _:reserve(),range(8)))
assert outcomes.count('GRANT_LIMIT_REACHED')==6, outcomes
with get_engine().connect() as c:
    assert c.execute(select(func.count()).where(provider_usage.c.grant_id==settings.cloud_grant_id)).scalar_one()==2
try:
    providers.reserve_call('knowledge','knowledge',Decimal(0))
    raise AssertionError('Knowledge phải bị chặn trước dispatch')
except AppError as error:
    assert error.code=='CALL_LIMIT_REACHED'""")

    def test_reserve_budget_and_unknown_usage_stop_before_another_call(self):
        self.run_quota("""assert reserve('0.04')=='GRANT_BUDGET_REACHED'
identifier=reserve()
from uuid import UUID
import httpx
sent=[]
with providers.request_client(httpx.MockTransport(lambda r: sent.append(r) or httpx.Response(503)),call_id=UUID(identifier)) as client:
    client.get('https://offline.invalid')
    try:
        client.get('https://offline.invalid')
        raise AssertionError('Không được dispatch lần hai')
    except AppError as error:
        assert error.code=='PROVIDER_RETRY_BLOCKED'
assert len(sent)==1
providers.finish_call(UUID(identifier),'error',1,error='PROVIDER_TEMPORARY')
with get_engine().connect() as c:
    assert c.execute(select(provider_usage.c.http_status).where(provider_usage.c.id==UUID(identifier))).scalar_one()==503
assert reserve()=='USAGE_UNKNOWN'""")

    def seed_review(self, *, status="error", evidence_status=400, snapshot_model=None):
        import json

        identifier = str(uuid4())
        model = "gemini-3.5-flash-lite"
        change = json.dumps({"model": snapshot_model}) if snapshot_model else "{}"
        evidence = json.dumps({"http_status": evidence_status, "reference": "offline_test"})
        postgres(
            f"INSERT INTO app.provider_usage(id,provider,model,status,reserved_cost_usd,grant_id,dispatch_count,error_code) "
            f"VALUES ('{identifier}','gemini','{model}','{status}',0.01,'{self.grant}',1,'PROVIDER_SCHEMA');"
            f"INSERT INTO app.provider_usage_reviews(usage_id,policy,accounted_reserve_usd,usage_snapshot,evidence,authority) "
            f"SELECT id,'retain_full_reserve',0.01,to_jsonb(u)||'{change}'::jsonb,'{evidence}','Offline test authority' FROM app.provider_usage u WHERE id='{identifier}';"
        )
        return identifier

    def test_review_retains_reserve_and_does_not_invent_usage(self):
        identifier = self.seed_review()
        self.run_quota("""assert reserve('0.025')=='GRANT_BUDGET_REACHED'
assert reserve() not in ('USAGE_UNKNOWN','GRANT_BUDGET_REACHED')
assert reserve()=='GRANT_LIMIT_REACHED'""")
        row = postgres(f"SELECT input_tokens IS NULL AND output_tokens IS NULL AND estimated_cost_usd IS NULL, reserved_cost_usd,status,dispatch_count FROM app.provider_usage WHERE id='{identifier}';")
        self.assertEqual(row.strip(), "t|0.01|error|1")

    def test_review_cannot_cover_inflight_mismatched_or_other_http_errors(self):
        for options in ({"status": "reserved"}, {"snapshot_model": "different"}, {"evidence_status": 503}):
            identifier = self.seed_review(**options)
            self.run_quota("assert reserve()=='USAGE_UNKNOWN'")
            postgres(f"DELETE FROM app.provider_usage_reviews WHERE usage_id='{identifier}'; DELETE FROM app.provider_usage WHERE id='{identifier}';")

    def test_runtime_cannot_self_approve_or_rewrite_reviews(self):
        identifier = self.seed_review()
        self.run_quota("""from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
for sql in ["INSERT INTO app.provider_usage_reviews SELECT * FROM app.provider_usage_reviews",
            "UPDATE app.provider_usage_reviews SET authority='forged'",
            "DELETE FROM app.provider_usage_reviews"]:
    try:
        with get_engine().begin() as c:
            c.execute(text(sql))
        raise AssertionError('Runtime must not mutate reviews')
    except DBAPIError as error:
        assert error.orig.sqlstate=='42501'""")

    def test_new_unknown_error_still_stops_after_old_review(self):
        self.seed_review()
        self.run_quota("""identifier=reserve()
from uuid import UUID
from sqlalchemy import update
with get_engine().begin() as c:
    c.execute(update(provider_usage).where(provider_usage.c.id==UUID(identifier)).values(dispatch_count=1,status='error',error_code='PROVIDER_SCHEMA'))
assert reserve()=='USAGE_UNKNOWN'""")

    def seed_503(self, *, http_status=503, error="PROVIDER_TEMPORARY", age=0):
        identifier = str(uuid4())
        postgres(
            "INSERT INTO app.provider_usage(id,provider,model,status,reserved_cost_usd,"
            "grant_id,dispatch_count,error_code,http_status,created_at) "
            f"VALUES ('{identifier}','gemini','gemini-3.5-flash-lite','error',0.01,"
            f"'{self.grant}',1,'{error}',{http_status},clock_timestamp()-interval '{age} seconds');"
        )
        return identifier

    def approve(self, identifier, **changes):
        from decimal import Decimal
        from operations.usage_review import review

        args = dict(usage_id=identifier, grant_id=self.grant, model="gemini-3.5-flash-lite",
                    reserve=Decimal("0.01"), authority="Offline test owner authorization", apply=True)
        args.update(changes)
        return review(**args)

    def test_verified_503_review_cooldown_and_original_ledger_unchanged(self):
        identifier = self.seed_503()
        before = postgres(f"SELECT to_jsonb(u) FROM app.provider_usage u WHERE id='{identifier}';")
        self.approve(identifier)
        self.run_quota("assert reserve()=='PROVIDER_COOLDOWN'")
        self.assertEqual(before, postgres(f"SELECT to_jsonb(u) FROM app.provider_usage u WHERE id='{identifier}';"))
        with self.assertRaises(RuntimeError):
            self.approve(identifier)
        # Tua đồng hồ fixture trước audit mới, không thay row/audit đã duyệt.
        postgres(f"DELETE FROM app.provider_usage_reviews WHERE usage_id='{identifier}'; DELETE FROM app.provider_usage WHERE id='{identifier}';")
        identifier = self.seed_503(age=65)
        self.approve(identifier)
        self.run_quota("assert reserve('0.025')=='GRANT_BUDGET_REACHED'\nassert reserve() not in ('USAGE_UNKNOWN','PROVIDER_COOLDOWN')\nassert reserve()=='GRANT_LIMIT_REACHED'")

    def test_review_rejects_wrong_grant_model_reserve_provider_or_untrusted_response(self):
        from decimal import Decimal

        identifier = self.seed_503(age=65)
        for changes in ({"grant_id": str(uuid4())}, {"model": "different"},
                        {"reserve": Decimal("0.02")}, {"authority": "no"}):
            with self.assertRaises(ValueError):
                self.approve(identifier, **changes)
        for assignment in ("provider='knowledge'", "http_status=NULL", "dispatch_count=0",
                           "status='reserved'", "error_code='PROVIDER_TIMEOUT'"):
            postgres(f"BEGIN; UPDATE app.provider_usage SET {assignment} WHERE id='{identifier}'; COMMIT;")
            with self.assertRaises(ValueError):
                self.approve(identifier)
            postgres(f"UPDATE app.provider_usage SET provider='gemini',http_status=503,dispatch_count=1,status='error',error_code='PROVIDER_TEMPORARY' WHERE id='{identifier}';")
        self.run_quota("assert reserve()=='USAGE_UNKNOWN'")

    def test_repeated_503_has_longer_cooldown_and_does_not_allow_new_unknown(self):
        for _ in range(2):
            self.approve(self.seed_503(age=65))
        # Hai lỗi đều tính request; nâng riêng cap fixture để kiểm cooldown.
        postgres(f"UPDATE app.provider_grants SET max_requests=4,budget_usd=0.1 WHERE id='{self.grant}';")
        self.run_quota("assert reserve()=='PROVIDER_COOLDOWN'")
        self.seed_503(age=65)
        self.run_quota("assert reserve()=='USAGE_UNKNOWN'")

    def test_generic_admin_review_is_bounded_and_snapshot_changes_block(self):
        postgres(f"UPDATE app.provider_grants SET max_requests=6,budget_usd=0.1 WHERE id='{self.grant}';")
        for _ in range(3):
            self.approve(self.seed_503(age=360))
        identifier = self.seed_503(age=360)
        with self.assertRaises(ValueError):
            self.approve(identifier)
        self.run_quota("assert reserve()=='USAGE_UNKNOWN'")
        # Toàn snapshot phải khớp, cả grant/provider/reserve và NULL usage.
        postgres(f"DELETE FROM app.provider_usage WHERE id='{identifier}'; UPDATE app.provider_usage SET reserved_cost_usd=0.02 WHERE grant_id='{self.grant}';")
        self.run_quota("assert reserve()=='USAGE_UNKNOWN'")
