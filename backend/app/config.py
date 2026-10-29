"""Giữ cấu hình provider; quyền gọi được kiểm tra tại từng tác vụ."""

from decimal import Decimal
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    database_url: SecretStr
    cloud_calls_allowed: bool = False
    cloud_max_requests: int = Field(default=0, ge=0)
    cloud_budget_usd: Decimal = Field(default=Decimal("0"), ge=0)
    gemini_enabled: bool = False
    knowledge_enabled: bool = False
    llamaparse_enabled: bool = False
    langfuse_enabled: bool = False
    session_secret: SecretStr = SecretStr("")
    google_client_id: str = ""
    app_origin: str = "http://localhost:18181"
    app_env: str = "development"
    storage_root: str = "/srv/chatsar/storage"
    reader_database_url: SecretStr = SecretStr("")

    @property
    def generation_allowed(self) -> bool:
        return self.cloud_calls_allowed and self.cloud_max_requests > 0


@lru_cache
def get_settings() -> Settings:
    return Settings()
