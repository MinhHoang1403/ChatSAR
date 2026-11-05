"""Bằng chứng xử lý owner-scoped; không chứa params thô hoặc gửi SQL vào trace."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from sqlalchemy.engine import Dialect

from app.query import CompiledQuery


@dataclass
class Processing:
    selected_provider: str
    source: dict[str, Any]
    stages: dict[str, dict[str, Any]] = field(default_factory=dict)
    sql: dict[str, Any] = field(
        default_factory=lambda: {
            "compiled": False,
            "statement": None,
            "dialect": "postgresql",
            "parameter_names": [],
            "execution_status": "not_started",
        }
    )
    provider: dict[str, Any] = field(default_factory=dict)
    failed_stage: str | None = None
    error_code: str | None = None
    current_stage: str | None = None

    @contextmanager
    def step(self, name: str) -> Iterator[None]:
        self.current_stage = name
        start = perf_counter()
        self.stages[name] = {"status": "in_progress"}
        try:
            yield
        except Exception:
            self.failed_stage = name
            self.stages[name]["status"] = "failed"
            raise
        else:
            self.stages[name]["status"] = "succeeded"
        finally:
            self.stages[name]["duration_ms"] = (perf_counter() - start) * 1000

    def capture_sql(self, compiled: CompiledQuery, dialect: Dialect) -> None:
        rendered = compiled.statement.compile(
            dialect=dialect, compile_kwargs={"render_postcompile": True}
        )
        # Chỉ giữ SQL có placeholders và tên bind. Không lưu rendered.params values.
        self.sql.update(
            compiled=True, statement=str(rendered), parameter_names=sorted(rendered.params)
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "evidence_format": 1,
            "source": self.source,
            "provider": self.provider,
            "selected_provider": self.selected_provider,
            "stages": self.stages,
            "failed_stage": self.failed_stage,
            "error_code": self.error_code,
            "sql": self.sql,
            "source_unchanged": True,
            "processed_at": datetime.now(UTC).isoformat(),
            "backend_timing_scope": (
                "Sau kiểm quyền, trước lưu kết quả cuối; không phải thời gian trình duyệt."
            ),
        }
