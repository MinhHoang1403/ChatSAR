"""Metadata SQLAlchemy Core khớp migrations do repository quản lý."""

from sqlalchemy import Column, DateTime, MetaData, String, Table, Uuid

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
