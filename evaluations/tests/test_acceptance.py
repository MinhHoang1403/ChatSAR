"""Dừng live ngay khi setup thất bại; giữ lý do trước khi dọn dữ liệu test."""

import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from evaluations import acceptance


class AcceptanceStopTests(unittest.TestCase):
    def test_rejected_setup_is_saved_exits_failed_and_never_sends_sql(self):
        class Session:
            def __init__(self):
                self.closed = False
                self.paths = []
                self.checksum = None

            def request(self, path, body=None, **options):
                self.paths.append(path)
                if path == "/workspaces":
                    return {"id": str(uuid4())}
                if path.endswith("/datasets"):
                    content = body.split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n--", 1)[0]
                    self.checksum = hashlib.sha256(content).hexdigest()
                    return {"dataset_id": str(uuid4()), "revision_id": str(uuid4())}
                if path.endswith("/preview"):
                    return {"checksum": self.checksum, "row_count": 1}
                if path.endswith("/setup"):
                    assert body["use_ai"] and body["provider"] == "gemini"
                    return {
                        "mode": "local",
                        "error_code": "SETUP_PROPOSAL_REJECTED",
                        "validation_errors": [],
                        "checksum": self.checksum,
                        "proposal": {"notes": ["Lý do từ chối cần được lưu"]},
                    }
                raise AssertionError(
                    "Không được gửi SQL hoặc gọi tiếp sau setup thất bại"
                )

            def close(self):
                self.closed = True

        session = Session()
        rows = [
            {
                "domain": "hotel",
                "rows": [
                    {
                        "booking_ref": "H01",
                        "room_type": "suite",
                        "nights": 1,
                        "room_charge": "100.05",
                        "checked_in": "2026-09-01",
                    }
                ],
            }
        ]
        baseline = {"gemini": 7, "knowledge": 5}
        after = {"gemini": 8, "knowledge": 5}
        artifacts = acceptance.ROOT / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=artifacts) as temporary:
            target = Path(temporary).resolve()
            self.assertTrue(
                target.is_relative_to((acceptance.ROOT / "artifacts").resolve())
            )
            with (
                patch.object(acceptance, "ROOT", target),
                patch.object(
                    acceptance, "ledger", side_effect=[baseline, baseline, after, after]
                ),
                patch.object(acceptance, "TestSession", return_value=session),
                patch.object(
                    acceptance,
                    "postgres",
                    return_value="\n".join(json.dumps(row) for row in rows),
                ),
                patch(
                    "sys.argv",
                    [
                        "acceptance",
                        "--live",
                        "--max-requests",
                        "3",
                        "--expected-ledger",
                        "12",
                    ],
                ),
                patch("builtins.print"),
                self.assertRaises(SystemExit) as error,
            ):
                acceptance.main()
            self.assertEqual(error.exception.code, 1)
            report = json.loads(
                (target / "artifacts" / "acceptance.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                report["cases"][0]["rejection_notes"], ["Lý do từ chối cần được lưu"]
            )
            self.assertEqual(report["generation_reservations"], 1)
            self.assertFalse(report["cases"][0]["pass"])
            self.assertTrue(session.closed)
            self.assertEqual(len([p for p in session.paths if p.endswith("/setup")]), 1)
