"""Tracing failure không thay kết quả nghiệp vụ và không đưa exception gốc vào trace."""

from unittest.mock import MagicMock, Mock

import pytest

from app import observability
from app.errors import AppError


def test_tracing_initialization_failure_does_not_interrupt_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        observability, "tracing_client", Mock(side_effect=RuntimeError("private detail"))
    )
    completed = []
    with observability.observation("offline") as span:
        assert span is None
        completed.append("business result")
    assert completed == ["business result"]


def test_trace_failure_retains_safe_error_code_and_original_business_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = MagicMock()
    span = context.__enter__.return_value
    client = Mock()
    client.start_as_current_observation.return_value = context
    monkeypatch.setattr(observability, "tracing_client", lambda: client)
    error = AppError(503, "PROVIDER_TIMEOUT", "private detail must stay out of traces")
    with pytest.raises(AppError) as captured:
        with observability.observation("offline"):
            raise error
    assert captured.value is error
    output = span.update.call_args.kwargs["output"]
    assert output["error_code"] == "PROVIDER_TIMEOUT"
    assert "private detail" not in str(span.update.call_args)
    context.__exit__.assert_called_once_with(None, None, None)
    span.update.side_effect = RuntimeError("tracing unavailable")
    with pytest.raises(AppError) as captured:
        with observability.observation("offline"):
            raise error
    assert captured.value is error
