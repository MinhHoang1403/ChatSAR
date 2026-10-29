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


def database_ready() -> bool:
    try:
        with get_engine().connect() as connection:
            version = connection.execute(
                text("SELECT name FROM app.schema_migrations WHERE name = 'foundation'")
            ).scalar_one_or_none()
        return version == "foundation"
    except SQLAlchemyError:
        # Không trả URL, credential hoặc thông báo DB ra endpoint công khai.
        return False
