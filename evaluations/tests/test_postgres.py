"""POC quyền reader và rollback trên chính PostgreSQL ChatSAR."""

import os
import subprocess
import unittest
from uuid import uuid4

from evaluations.oracle import ROOT, postgres


@unittest.skipUnless(os.getenv("CHATSAR_POSTGRES_TESTS") == "1", "Chạy riêng với PostgreSQL thật")
class PostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.table = "r_" + uuid4().hex
        postgres(
            f"SET ROLE chatsar_app; CREATE TABLE data.{cls.table} "
            "(code TEXT PRIMARY KEY, amount NUMERIC(18,2)); "
            f"INSERT INTO data.{cls.table} VALUES ('0007', 0.10), ('0012', 0.20), ('0100', NULL); "
            f"GRANT SELECT ON data.{cls.table} TO chatsar_reader;"
        )

    @classmethod
    def tearDownClass(cls) -> None:
        # Chỉ xóa bảng tổng hợp có tên ngẫu nhiên được chính test này vừa tạo.
        postgres(f"SET ROLE chatsar_app; DROP TABLE data.{cls.table};")

    def reader(self, sql: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["docker", "compose", "exec", "-T", "db", "sh", "-c",
             'PGPASSWORD="$CHATSAR_READER_PASSWORD" exec psql -X -qAt -h 127.0.0.1 '
             '-U chatsar_reader -d chatsar -v ON_ERROR_STOP=1 -v VERBOSITY=sqlstate'],
            input=sql, text=True, encoding="utf-8", capture_output=True,
            cwd=ROOT, timeout=15, check=False,
        )

    def test_reader_is_restricted_and_defaults_to_read_only(self) -> None:
        result = self.reader("SHOW default_transaction_read_only; SHOW statement_timeout;")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().splitlines(), ["on", "5s"])
        flags = postgres(
            "SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls "
            "FROM pg_roles WHERE rolname='chatsar_reader';"
        )
        self.assertEqual(flags.strip(), "f")

    def test_reader_preserves_decimal_null_and_text(self) -> None:
        result = self.reader(
            f"SELECT code, COALESCE(amount::text, 'NULL') FROM data.{self.table} ORDER BY code;"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().splitlines(), ["0007|0.10", "0012|0.20", "0100|NULL"])

    def test_reader_cannot_write_even_if_read_only_default_is_overridden(self) -> None:
        for statement in [
            f"INSERT INTO data.{self.table} VALUES ('forbidden', 1)",
            f"UPDATE data.{self.table} SET amount=9",
            f"DELETE FROM data.{self.table}",
            "CREATE TABLE data.forbidden (id INT)",
            "CREATE TEMP TABLE forbidden (id INT)",
            "SELECT * FROM app.schema_migrations",
        ]:
            with self.subTest(statement=statement.split()[0]):
                result = self.reader("BEGIN READ WRITE; " + statement + "; ROLLBACK;")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("42501", result.stderr)

    def test_ddl_rollback_leaves_no_half_published_table(self) -> None:
        name = "r_" + uuid4().hex
        output = postgres(
            f"BEGIN; SET LOCAL ROLE chatsar_app; CREATE TABLE data.{name}(id INT); ROLLBACK; "
            f"SELECT to_regclass('data.{name}') IS NULL;"
        )
        self.assertEqual(output.strip(), "t")

    def test_reader_query_timeout_is_enforced(self) -> None:
        result = self.reader("SELECT pg_sleep(6);")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("57014", result.stderr)

    def test_scalar_null_aggregate_equivalence_does_not_extend_to_count_rows(self) -> None:
        result = postgres("WITH t(v) AS (VALUES(NULL::numeric),(1),(1),(0)) "
                          "SELECT (SELECT ROW(COUNT(DISTINCT v),COUNT(v),SUM(v),AVG(v),MIN(v),MAX(v)) FROM t) "
                          "IS NOT DISTINCT FROM (SELECT ROW(COUNT(DISTINCT v),COUNT(v),SUM(v),AVG(v),MIN(v),MAX(v)) FROM t WHERE v IS NOT NULL), "
                          "(SELECT COUNT(*) FROM t) <> (SELECT COUNT(*) FROM t WHERE v IS NOT NULL);")
        self.assertEqual(result.strip(), "t|t")


if __name__ == "__main__":
    unittest.main()
