"""Adapter offline không được gọi mạng, retry/fallback hay bịa usage."""

import json
import socket
from contextlib import nullcontext
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import httpx
import pytest
from google.genai._gaos.lib.compat_errors import APITimeoutError
from pydantic import SecretStr

from app import providers
from app.config import Settings
from app.errors import AppError
from app.query import QueryPlan


@pytest.fixture
def adapter(monkeypatch: pytest.MonkeyPatch) -> tuple[Settings, dict, Mock, Mock]:
    settings = Settings(
        database_url=SecretStr("postgresql://unused"),
        gemini_api_key=SecretStr("offline-placeholder"),
        gemini_enabled=True,
        knowledge_enabled=True,
    )
    reserve, finish = Mock(), Mock()
    monkeypatch.setattr(providers, "get_settings", lambda: settings)
    monkeypatch.setattr(providers, "reserve_call", reserve)
    monkeypatch.setattr(providers, "finish_call", finish)
    monkeypatch.setattr(providers, "observation", lambda *a, **k: nullcontext(None))
    revision = {
        "data_classification": "synthetic",
        "id": "r",
        "dataset_id": "d",
        "timezone": "UTC",
        "grain": "row",
        "columns": [],
    }
    return settings, revision, reserve, finish


def test_knowledge_no_auth_header_and_unknown_usage_stays_null(
    adapter: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, revision, reserve, finish = adapter
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        assert "Authorization" not in request.headers
        return httpx.Response(
            200, json={"choices": [{"message": {"content": '{"task":"CLARIFY"}'}}]}
        )

    factory = httpx.Client
    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda **kw: factory(**kw, transport=httpx.MockTransport(handler)),
    )
    result = providers.generate_proposal("?", revision, "knowledge")
    assert result.input_tokens is None and result.output_tokens is None
    assert len(captured) == reserve.call_count == finish.call_count == 1
    assert str(captured[0].url) == "https://ai.inetcloud.vn/memochat/v1/chat/completions"


def test_knowledge_403_one_call_and_classified(
    adapter: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, revision, _, finish = adapter
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(403, json={"error": "Forbidden"})

    factory = httpx.Client
    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda **kw: factory(**kw, transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(AppError) as error:
        providers.generate_proposal("?", revision, "knowledge")
    assert error.value.code == "PROVIDER_FORBIDDEN"
    assert len(captured) == finish.call_count == 1


def test_gemini_interactions_contract_and_no_automatic_extra_calls(
    adapter: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, revision, reserve, _ = adapter
    create = Mock(
        return_value=SimpleNamespace(output_text='{"task":"CLARIFY"}', id="offline", usage=None)
    )

    def client(**kw: object) -> object:
        assert kw["http_options"].retry_options.attempts == 0
        return nullcontext(SimpleNamespace(interactions=SimpleNamespace(create=create)))

    monkeypatch.setattr(providers.genai, "Client", client)
    result = providers.generate_proposal("?", revision, "gemini")
    assert result.input_tokens is None
    assert create.call_count == reserve.call_count == 1
    assert create.call_args.kwargs["store"] is False
    assert create.call_args.kwargs["automatic_continuation"] is False
    assert create.call_args.kwargs["response_format"]["mime_type"] == "application/json"


def test_private_dataset_denied_before_reserving_or_network(adapter: tuple) -> None:
    _, revision, reserve, _ = adapter
    revision["data_classification"] = "private"
    with pytest.raises(AppError) as error:
        providers.generate_proposal("?", revision, "gemini")
    assert error.value.code == "DATA_PERMISSION_REQUIRED"
    reserve.assert_not_called()


def test_schema_projection_preserves_runtime_caps() -> None:
    schema = providers.response_schema()
    assert "maxItems" not in json.dumps(schema)
    assert QueryPlan.model_json_schema()["properties"]["select_columns"]["maxItems"] == 30


def test_incomplete_sql_plan_is_rejected_and_usage_retained(
    adapter: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, revision, _, finish = adapter
    factory = httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"task":"SQL"}'}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7},
            },
        )

    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda **kw: factory(**kw, transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(AppError) as error:
        providers.generate_proposal("?", revision, "knowledge")
    assert error.value.code == "PROVIDER_SCHEMA"
    assert finish.call_args.args[3:5] == (11, 7)


@pytest.mark.parametrize(
    "total,budget,expected",
    [(10, "10", "CALL_LIMIT_REACHED"), (0, "0", "BUDGET_REACHED"), (0, "0.01", "BUDGET_REACHED")],
)
def test_durable_budget_guard_denies_before_reserving(
    monkeypatch: pytest.MonkeyPatch, total: int, budget: str, expected: str
) -> None:
    settings = Settings(
        database_url=SecretStr("postgresql://unused"),
        cloud_calls_allowed=True,
        cloud_max_requests=10,
        cloud_budget_usd=Decimal(budget),
    )
    connection = MagicMock()
    connection.execute.side_effect = [
        Mock(),
        Mock(scalar_one=lambda: total),
        Mock(scalar_one=lambda: 0),
        Mock(scalar_one=lambda: Decimal(0)),
    ]
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value = connection
    monkeypatch.setattr(providers, "get_settings", lambda: settings)
    monkeypatch.setattr(providers.db, "get_engine", lambda: engine)
    with pytest.raises(AppError) as error:
        providers.reserve_call("gemini", "gemini-3.5-flash-lite", Decimal("0.02"))
    assert error.value.code == expected
    assert connection.execute.call_count <= 4


@pytest.mark.parametrize("provider_count,accepted", [(5, True), (10, False)])
def test_total_and_provider_limits_are_separate(
    monkeypatch: pytest.MonkeyPatch, provider_count: int, accepted: bool
) -> None:
    settings = Settings(
        database_url=SecretStr("postgresql://unused"),
        cloud_calls_allowed=True,
        cloud_max_requests=12,
        cloud_budget_usd=Decimal("10"),
    )
    connection = MagicMock()
    connection.execute.side_effect = [
        Mock(),
        Mock(scalar_one=lambda: 10),
        Mock(scalar_one=lambda: provider_count),
        Mock(scalar_one=lambda: Decimal(0)),
        Mock(),
    ]
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value = connection
    monkeypatch.setattr(providers, "get_settings", lambda: settings)
    monkeypatch.setattr(providers.db, "get_engine", lambda: engine)
    if accepted:
        assert (
            providers.reserve_call("gemini", "gemini-3.5-flash-lite", Decimal("0.02")) is not None
        )
        assert connection.execute.call_count == 5
    else:
        with pytest.raises(AppError) as error:
            providers.reserve_call("gemini", "gemini-3.5-flash-lite", Decimal("0.02"))
        assert error.value.code == "CALL_LIMIT_REACHED"


@pytest.mark.parametrize("failure", [503, 429, "timeout"])
def test_real_sdk_transport_does_not_retry(
    monkeypatch: pytest.MonkeyPatch, failure: int | str
) -> None:
    requests: list[httpx.Request] = []

    def forbid_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("Offline test attempted network access")

    monkeypatch.setattr(socket.socket, "connect", forbid_network)

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("offline", request=request)
        return httpx.Response(
            int(failure),
            json={"error": {"code": int(failure), "message": "offline", "status": "UNAVAILABLE"}},
        )

    with providers.request_client(httpx.MockTransport(handler)) as transport:
        with providers.genai.Client(
            api_key="offline-placeholder",
            http_options=providers.types.HttpOptions(
                base_url="https://offline.invalid",
                httpx_client=transport,
                retry_options=providers.types.HttpRetryOptions(attempts=0),
                timeout=1000,
            ),
        ) as client:
            with pytest.raises((AppError, APITimeoutError)) as error:
                client.interactions.create(
                    model="gemini-3.5-flash-lite",
                    input="offline",
                    automatic_continuation=False,
                    store=False,
                    timeout=1,
                )
            if failure == "timeout":
                assert isinstance(error.value, APITimeoutError)
            else:
                assert isinstance(error.value, AppError)
                assert error.value.code == "PROVIDER_RETRY_BLOCKED"
    assert len(requests) == 1
