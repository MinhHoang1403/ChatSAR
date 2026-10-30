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
assert reserve()=='USAGE_UNKNOWN'""")
