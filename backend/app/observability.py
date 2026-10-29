"""Trace metadata của thao tác thật; lỗi tracing không thay đổi nghiệp vụ."""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from langfuse import Langfuse

from app.config import get_settings


@lru_cache
def tracing_client() -> Langfuse | None:
    settings = get_settings()
    if not settings.langfuse_enabled:
        return None
    public = settings.langfuse_public_key.get_secret_value()
    secret = settings.langfuse_secret_key.get_secret_value()
    if not public or not secret or not settings.langfuse_base_url:
        return None
    url = urlsplit(settings.langfuse_base_url)
    if Path("/.dockerenv").exists() and url.hostname in ("127.0.0.1", "localhost"):
        # Đổi địa chỉ loopback theo network Docker, không ghi đè cấu hình local.
        url = url._replace(netloc="host.docker.internal:" + str(url.port or 3000))
    return Langfuse(
        public_key=public,
        secret_key=secret,
        base_url=urlunsplit(url),
        timeout=3,
        debug=False,
        environment="development",
    )


@contextmanager
def observation(name: str, **metadata: Any) -> Iterator[Any]:
    context = None
    try:
        client = tracing_client()
        if client is not None:
            context = client.start_as_current_observation(
                as_type="span", name=name, metadata=metadata
            )
            span = context.__enter__()
    except Exception:
        context = None
    if context is None:
        yield None
        return
    try:
        yield span
    except Exception as error:
        # Không giao exception gốc cho SDK vì có thể chứa SQL/giá trị riêng tư.
        annotate(
            span, output={"status": "failed", "error_type": type(error).__name__}, level="ERROR"
        )
        raise
    finally:
        try:
            context.__exit__(None, None, None)
        except Exception:
            pass


def current_trace_id() -> str | None:
    try:
        client = tracing_client()
        return client.get_current_trace_id() if client is not None else None
    except Exception:
        return None


def flush_observations() -> None:
    if not tracing_client.cache_info().currsize:
        return
    try:
        client = tracing_client()
        if client is not None:
            client.flush()
    except Exception:
        pass


def annotate(span: Any, **fields: Any) -> None:
    if span is not None:
        try:
            span.update(**fields)
        except Exception:
            pass
