"""Metadata SQLAlchemy Core khớp migrations do repository quản lý."""

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Uuid
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData(schema="app")
users = Table(
    "users",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("provider", String),
    Column("provider_subject", String),
    Column("display_name", String),
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
