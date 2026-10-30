"""So sánh cấu trúc planning offline; không suy model quality từ fixture tự tạo."""

import json

from evaluations.persistence import inside


def main() -> None:
    output = inside("""
import json
from pydantic import ValidationError
from app.query import QueryPlan
from app.planning import QueryRequest
from app.providers import response_schema
schema=response_schema()
candidate_schema=response_schema(QueryRequest)
original=QueryPlan.model_json_schema()
sample={"task":"SQL","table_id":"dataset","source_revision_id":"revision","raw_user_spans":["Tổng"],"coverage":["Tổng"],"aggregations":[{"operator":"SUM","column_id":"amount","output_id":"total"}]}
mutations=[{}, {"sql":"SELECT 1"},{"table_id":""},{"limit":"2"},{"limit":501},{"aggregations":[]},{"filters":{"operator":"DROP"}},{"raw_user_spans":[]}]
counts={"single":{"accepted":0,"rejected":0},"two_stage_reassembled":{"accepted":0,"rejected":0}}
for change in mutations:
 proposal={**sample,**change}
 # Chỉ tách/ghép fixture để so consistency; không có model ở hai bước này.
 intent={k:v for k,v in proposal.items() if k not in ("table_id","source_revision_id")}
 binding={k:v for k,v in proposal.items() if k in ("table_id","source_revision_id")}
 for name,candidate in (("single",proposal),("two_stage_reassembled",{**intent,**binding})):
  try:
   QueryPlan.model_validate(candidate)
   counts[name]["accepted"]+=1
  except ValidationError:
   counts[name]["rejected"]+=1
print(json.dumps({"offline_fixture_consistency":counts,"internal_schema_bytes":len(json.dumps(original).encode()),"candidate_schema_bytes":len(json.dumps(candidate_schema).encode()),"provider_schema_bytes":len(json.dumps(schema).encode()),"internal_properties":len(original["properties"]),"provider_properties":len(schema["properties"]),"current_provider_contract":"QueryPlan; QueryRequest is an offline candidate only","model_quality_comparison":"NOT_RUN","model_tokens":None,"model_latency":None,"model_cost":None,"decision":"one_call; no measured quality gain justifies two paid calls"}))
""")
    print(json.dumps(json.loads(output), indent=2))


if __name__ == "__main__":
    main()
