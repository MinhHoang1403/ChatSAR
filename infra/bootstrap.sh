#!/bin/sh
set -eu

# Chỉ chạy khi volume ChatSAR mới được khởi tạo. Không in mật khẩu ra log.
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set ON_ERROR_STOP=1 \
  --set app_password="$CHATSAR_APP_PASSWORD" \
  --set reader_password="$CHATSAR_READER_PASSWORD" <<'SQL'
CREATE ROLE chatsar_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD :'app_password';
CREATE ROLE chatsar_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD :'reader_password';
REVOKE ALL ON DATABASE chatsar FROM PUBLIC;
GRANT CONNECT ON DATABASE chatsar TO chatsar_app, chatsar_reader;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA app AUTHORIZATION chatsar_admin;
CREATE SCHEMA data AUTHORIZATION chatsar_app;
GRANT USAGE ON SCHEMA app TO chatsar_app;
GRANT USAGE ON SCHEMA data TO chatsar_reader;
ALTER ROLE chatsar_reader SET default_transaction_read_only = on;
ALTER ROLE chatsar_reader SET statement_timeout = '5s';
ALTER ROLE chatsar_reader SET lock_timeout = '1s';
CREATE EXTENSION vector;
SQL
