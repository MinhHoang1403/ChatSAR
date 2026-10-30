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
        snapshot = json.dumps({"status": status, "error_code": "PROVIDER_SCHEMA",
                               "model": snapshot_model or model, "dispatch_count": 1})
        evidence = json.dumps({"http_status": evidence_status, "reference": "offline_test"})
        postgres(
            f"INSERT INTO app.provider_usage(id,provider,model,status,reserved_cost_usd,grant_id,dispatch_count,error_code) "
            f"VALUES ('{identifier}','gemini','{model}','{status}',0.01,'{self.grant}',1,'PROVIDER_SCHEMA');"
            f"INSERT INTO app.provider_usage_reviews(usage_id,policy,accounted_reserve_usd,usage_snapshot,evidence,authority) "
            f"VALUES ('{identifier}','retain_full_reserve',0.01,'{snapshot}','{evidence}','Offline test authority');"
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
