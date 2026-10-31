"""Review bảo thủ một phản hồi 503 đã ghi nhận, bằng role admin ngoài API.

Mặc định chỉ preview. Không gọi provider, không sửa ledger/grant hoặc usage cũ.
"""

import argparse
import json
import subprocess
from decimal import Decimal
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]


def postgres(sql: str) -> str:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "db",
            "psql",
            "-X",
            "-qAt",
            "-U",
            "chatsar_admin",
            "-d",
            "chatsar",
            "-v",
            "ON_ERROR_STOP=1",
        ],
        input=sql,
        text=True,
        encoding="utf-8",
        capture_output=True,
        cwd=ROOT,
        timeout=30,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("Review không được ghi: " + result.stderr.strip())
    return result.stdout.strip()


def quoted(value: str) -> str:
    # psql nhận SQL qua stdin; không nội suy vào shell, không xử lý backslash.
    return "'" + value.replace("'", "''") + "'"


def review(
    usage_id: str,
    grant_id: str,
    model: str,
    reserve: Decimal,
    authority: str,
    *,
    apply: bool = False,
) -> dict:
    usage_id, grant_id = str(UUID(usage_id)), str(UUID(grant_id))
    if not 10 <= len(authority) <= 1000 or not reserve.is_finite() or reserve <= 0:
        raise ValueError("Cần quyền cụ thể và reserve dương hữu hạn")
    row = json.loads(
        postgres(
            "SELECT row_to_json(u) FROM app.provider_usage u WHERE id="
            + quoted(usage_id)
        )
        or "null"
    )
    if not row or any(
        (
            row["grant_id"] != grant_id,
            row["model"] != model,
            row["provider"] != "gemini",
            row["status"] != "error",
            row["error_code"] != "PROVIDER_TEMPORARY",
            row["dispatch_count"] != 1,
            row["http_status"] != 503,
            row["estimated_cost_usd"] is not None,
            any(
                row[k] is not None
                for k in ("input_tokens", "output_tokens", "thought_tokens")
            ),
            Decimal(str(row["reserved_cost_usd"])) != reserve,
        )
    ):
        raise ValueError("Snapshot/evidence không đủ điều kiện review 503")
    evidence = {
        "http_status": 503,
        "source": "httpx_response_hook",
        "usage": "UNKNOWN",
        "billing": "NOT_VERIFIED",
    }
    snapshot = quoted(json.dumps(row)) + "::jsonb"
    payload = {
        "usage_id": usage_id,
        "grant_id": grant_id,
        "snapshot": row,
        "evidence": evidence,
        "authority": authority,
        "applied": False,
    }
    if apply:
        # Cùng advisory lock với reserve; so lại toàn row trong transaction.
        # UNIQUE usage_id không cho review trùng hoặc ghi đè audit trước.
        output = postgres(
            "BEGIN; SELECT pg_advisory_xact_lock(193167598); "
            "INSERT INTO app.provider_usage_reviews "
            "(usage_id,policy,accounted_reserve_usd,usage_snapshot,evidence,authority) "
            "SELECT u.id,'retain_full_reserve',u.reserved_cost_usd,to_jsonb(u),"
            + quoted(json.dumps(evidence))
            + "::jsonb,"
            + quoted(authority)
            + " FROM app.provider_usage u JOIN app.provider_grants g ON g.id=u.grant_id "
            "WHERE u.id="
            + quoted(usage_id)
            + " AND to_jsonb(u)="
            + snapshot
            + " AND g.provider='gemini' AND g.max_requests<=100 AND g.budget_usd<=1.50 "
            "AND (SELECT count(*) FROM app.provider_usage WHERE grant_id=g.id)<=g.max_requests "
            "AND (SELECT sum(reserved_cost_usd) FROM app.provider_usage "
            "WHERE grant_id=g.id)<=g.budget_usd "
            "AND (SELECT count(*) FROM app.provider_usage_reviews r JOIN app.provider_usage p "
            "ON p.id=r.usage_id WHERE p.grant_id=g.id AND p.http_status=503)<3 "
            "RETURNING usage_id; COMMIT;"
        )
        if usage_id not in output.splitlines():
            raise ValueError(
                "Snapshot đổi, hết hạn mức hoặc đã đạt giới hạn 3 review 503/grant"
            )
        payload["applied"] = True
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--usage-id", required=True)
    parser.add_argument("--grant-id", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--reserve", required=True, type=Decimal)
    parser.add_argument("--authority", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            review(
                args.usage_id,
                args.grant_id,
                args.model,
                args.reserve,
                args.authority,
                apply=args.apply,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
