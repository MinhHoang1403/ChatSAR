# Vận hành nền tảng ChatSAR

Chỉ chạy tại root repository chính. Một Compose project `chatsar`, volume `chatsar_database`, không có test/staging project thứ hai. DB không publish port ra host. Web `http://localhost:18181`; API health `http://127.0.0.1:18081/health`. Kiểm tra lại port trước mỗi lần khởi động nếu môi trường đã thay đổi.

## Cấu hình local

`.env.example` chỉ chứa placeholder và provider OFF/budget 0. `.env` local bị Git bỏ qua. Mật khẩu DB/session phải ngẫu nhiên riêng cho ChatSAR. Không in `docker compose config` đầy đủ vì có thể lộ secrets; dùng `docker compose config --quiet` để kiểm tra cấu hình.

Chủ dự án có thể điền `GOOGLE_CLIENT_ID`, `KNOWLEDGE_BASE_URL`, các biến `LANGFUSE_*` vào `.env`, không gửi secrets qua chat. Google Web Client mới cần origin `http://localhost:18181`; cấu hình production HTTPS riêng sẽ được chốt sau. Không sửa OAuth client ShopQuery. Giữ nguyên flags enabled do người dùng đặt; mỗi tác vụ phải kiểm tra quyền và hạn mức riêng. Smoke tests Gemini/Knowledge tối đa 10 calls/provider hoặc giới hạn thấp hơn trong cấu hình. LlamaParse enabled không cấp quyền parse ở Phase 1. Không ghi đè .env.

## Các lệnh chính

```powershell
# Dependency phát triển trong cùng repository, theo lockfiles.
uv sync --project backend --frozen
npm.cmd ci --ignore-scripts --prefix frontend

# Khởi động DB duy nhất và áp dụng migration.
docker compose up -d --wait db
Get-Content backend/migrations/foundation.sql -Raw -Encoding UTF8 | docker compose exec -T db psql -X -q -U chatsar_admin -d chatsar -v ON_ERROR_STOP=1

# Chỉ build khi source/dependency/Dockerfile thay đổi.
docker compose build
docker compose up -d --wait

# Oracle/permissions thật; không dùng mock thay model-live.
$env:CHATSAR_POSTGRES_TESTS = '1'
py -3.11 -m unittest discover -s evaluations/tests -v
py -3.11 -m evaluations.oracle
py -3.11 -m evaluations.runtime

# Kiểm tra code trong backend: uv run --frozen ruff check app tests
# Format: uv run --frozen ruff format --check app tests
# Types: uv run --frozen mypy
# Unit: uv run --frozen pytest -q
# Frontend: npm.cmd run typecheck; npm.cmd run build (trong frontend/)

# Dừng đúng ChatSAR khi cần, giữ nguyên volume.
docker compose stop
```

Không chạy `down -v`, prune volumes, restart dịch vụ khác hoặc dùng rollback Git thay backup dữ liệu. Bootstrap roles chỉ chạy với volume mới; thay mật khẩu trong `.env` sau khi DB đã tạo không tự đổi mật khẩu DB. Migration dùng role admin trong DB service; API chỉ nhận app credential. Không truyền admin URL vào API container.

Các bước backup/restore đầy đủ chưa được nghiệm thu ở F1; phải bổ sung theo milestone có dữ liệu người dùng trước khi tuyên bố release an toàn. Hiện các bảng benchmark được nạp trong transaction rồi rollback; tests quyền chỉ tạo/xóa đúng bảng tổng hợp có ID ngẫu nhiên của lần chạy.
