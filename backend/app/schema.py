"""Metadata SQLAlchemy Core khớp migrations do repository quản lý."""

from sqlalchemy import Column, DateTime, Float, Integer, MetaData, Numeric, String, Table, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData(schema="app")
users = Table(
    "users",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("provider", String),
    Column("provider_subject", String),
    Column("display_name", String),
    Column("phone", String),
    Column("interests", String),
)
sessions = Table(
    "sessions",
    metadata,
    Column("token_hash", String, primary_key=True),
    Column("user_id", Uuid),
    Column("expires_at", DateTime(timezone=True)),
    Column("revoked_at", DateTime(timezone=True)),
    Column("google_nonce_hash", String),
)
workspaces = Table(
    "workspaces",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("owner_id", Uuid),
    Column("name", String),
    Column("created_at", DateTime(timezone=True)),
)

datasets = Table(
    "datasets",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid),
    Column("name", String),
    Column("checksum", String),
)
revisions = Table(
    "dataset_revisions",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("dataset_id", Uuid),
    Column("status", String),
    Column("storage_name", String),
    Column("suffix", String),
    Column("sheet_name", String),
    Column("columns", JSONB),
    Column("physical_table", String),
    Column("row_count", Integer),
    Column("timezone", String),
    Column("grain", String),
    Column("data_classification", String),
    Column("description", String),
    Column("sharing_providers", JSONB),
    Column("setup_proposal", JSONB),
    Column("created_at", DateTime(timezone=True)),
)
jobs = Table(
    "ingestion_jobs",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("revision_id", Uuid),
    Column("status", String),
    Column("error_code", String),
    Column("updated_at", DateTime(timezone=True)),
)

conversations = Table(
    "conversations",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("workspace_id", Uuid),
    Column("title", String),
    Column("revision_id", Uuid),
    Column("created_at", DateTime(timezone=True)),
)
messages = Table(
    "messages",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("conversation_id", Uuid),
    Column("revision_id", Uuid),
    Column("question", String),
    Column("request_key", String),
    Column("request_hash", String),
    Column("provider", String),
    Column("status", String),
    Column("envelope", JSONB),
    Column("query_plan", JSONB),
    Column("created_at", DateTime(timezone=True)),
)
results = Table(
    "result_records",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("message_id", Uuid),
    Column("envelope", JSONB),
)
provider_usage = Table(
    "provider_usage",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("provider", String),
    Column("model", String),
    Column("status", String),
    Column("input_tokens", Integer),
    Column("output_tokens", Integer),
    Column("thought_tokens", Integer),
    Column("estimated_cost_usd", Numeric),
    Column("reserved_cost_usd", Numeric),
    Column("latency_ms", Float),
    Column("error_code", String),
    Column("created_at", DateTime(timezone=True)),
    Column("grant_id", Uuid),
    Column("dispatch_count", Integer),
)

provider_grants = Table(
    "provider_grants",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("provider", String),
    Column("baseline", JSONB),
    Column("max_requests", Integer),
    Column("budget_usd", Numeric),
    Column("created_at", DateTime(timezone=True)),
)
