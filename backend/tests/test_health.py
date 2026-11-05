"""Kiểm tra trạng thái DB lỗi và việc health không tiết lộ cấu hình."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost/unused")
    get_settings.cache_clear()
    return TestClient(create_app(recover_jobs=False))


def test_live_does_not_require_database(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected_database_call() -> bool:
        raise AssertionError("Liveness không được phụ thuộc DB")

    monkeypatch.setattr("app.main.database_ready", unexpected_database_call)
    with client:
        response = client.get("/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert str(UUID(response.json()["request_id"])) == response.headers["X-Request-ID"]


@pytest.mark.parametrize("path", ["/ready", "/health"])
def test_readiness_fails_closed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    monkeypatch.setattr("app.main.database_ready", lambda: False)
    with client:
        response = client.get(path)
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert "DATABASE_URL" not in response.text
    assert "unused" not in response.text


def test_health_reports_no_paid_calls(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.database_ready", lambda: True)
    with client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["cloud_calls_allowed"] is False


@pytest.mark.parametrize(
    "setting,value",
    [
        ("CLOUD_CALLS_ALLOWED", "true"),
        ("CLOUD_MAX_REQUESTS", "1"),
        ("CLOUD_BUDGET_USD", "1"),
        ("GEMINI_ENABLED", "true"),
        ("KNOWLEDGE_ENABLED", "true"),
        ("LLAMAPARSE_ENABLED", "true"),
    ],
)
def test_provider_configuration_is_preserved_without_implicit_calls(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, setting: str, value: str
) -> None:
    monkeypatch.setenv(setting, value)
    get_settings.cache_clear()
    with client:
        assert client.get("/live").status_code == 200
    assert getattr(get_settings(), setting.lower()) in (True, 1)


def test_invalid_configuration_never_prints_input_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pydantic import ValidationError

    from app.config import Settings

    sentinel = "credential_mistakenly_pasted_into_boolean"
    monkeypatch.setenv("LANGFUSE_ENABLED", sentinel)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost/unused")
    with pytest.raises(ValidationError) as error:
        Settings()
    assert sentinel not in str(error.value)
