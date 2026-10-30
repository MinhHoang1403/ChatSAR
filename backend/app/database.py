"""Kết nối app role và kiểm tra migration; không gọi provider từ health."""

from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(
        get_settings().database_url.get_secret_value(),
        pool_size=2,
        max_overflow=0,
        pool_timeout=3,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 3},
        hide_parameters=True,
    )


@lru_cache
def get_reader_engine() -> Engine:
    return create_engine(
        get_settings().reader_database_url.get_secret_value(),
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
        pool_timeout=3,
        hide_parameters=True,
        connect_args={"connect_timeout": 3},
    )


def database_ready() -> bool:
    try:
        with get_engine().connect() as connection:
            versions = set(
                connection.execute(text("SELECT name FROM app.schema_migrations")).scalars()
            )
        return {
            "foundation",
            "identity",
            "datasets",
            "conversation",
            "catalog",
            "provider_grants",
            "chat_management",
        } <= versions
    except SQLAlchemyError:
        # Không trả URL, credential hoặc thông báo DB ra endpoint công khai.
        return False
