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
foreach ($name in @('foundation','identity','datasets','conversation')) {
  Get-Content "backend/migrations/$name.sql" -Raw -Encoding UTF8 | docker compose exec -T db psql -X -q -U chatsar_admin -d chatsar -v ON_ERROR_STOP=1
  if ($LASTEXITCODE -ne 0) { throw "Migration thất bại: $name" }
}

# Chỉ build khi source/dependency/Dockerfile thay đổi.
docker compose build
docker compose up -d --wait

# Oracle/permissions thật; không dùng mock thay model-live.
$env:CHATSAR_POSTGRES_TESTS = '1'
py -3.11 -m unittest discover -s evaluations/tests -v
py -3.11 -m evaluations.oracle
py -3.11 -m evaluations.runtime
py -3.11 -m evaluations.integration
py -3.11 -m evaluations.model_live --providers gemini --cases logistics_sum hotel_sum library_sum --prepare-only
py -3.11 -m evaluations.persistence

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

## Chat, cloud và tracing

Sau Google login: tạo/chọn workspace → tải CSV/XLSX → review kiểu/NULL/timezone → xác nhận → mở bộ dữ liệu ready → chọn mô hình và gửi câu hỏi. Dữ liệu private không được gửi model; chỉ chọn synthetic cho dữ liệu thực sự tổng hợp. Khi đổi nguồn của conversation đã có câu trả lời, tạo conversation mới. Lịch sử và kết quả được lưu trong PostgreSQL; không dùng localStorage để lưu session.

Origin browser phải trùng `APP_ORIGIN`: `localhost` và `127.0.0.1` là hai origin khác nhau. Giao diện đọc origin chuẩn từ `/api/auth/config` rồi chuyển về đó trước khi khởi tạo Google Login. Không nới allowlist/CSRF để chấp nhận tùy ý các origin. Sau đổi cấu hình local cần `docker compose up -d --wait` để container nạp lại; không build lại image chỉ vì đổi `.env`.

`evaluations.model_live --prepare-only` chỉ kiểm fidelity dữ liệu qua HTTP, không gọi model. Bỏ cờ này sẽ gọi provider thật: chỉ được chạy khi có hạn mức còn lại và quyền rõ ràng. Không chạy lệnh live để kiểm health. Đã dùng đủ 10 reservations của cấu hình hiện tại; không tự xóa ledger/reset bộ đếm/tăng `.env` để chạy thêm. Lỗi và timeout vẫn tính reservation; số HTTP request lịch sử trước khi sửa SDK guard chưa được xác minh đầy đủ, xem PREFLIGHT.

Langfuse dùng server hiện hữu; API container tự đổi localhost thành host.docker.internal chỉ trong bộ nhớ. Không sửa `.env`, không tạo service mới. SDK 5 dùng OTEL ingestion và Observations API v2; `/api/public/traces` cũ có thể trả 404. Chẩn đoán chỉ đọc field metadata do ChatSAR đặt, không in metadata SDK toàn bộ vì có thể chứa public key. `artifacts/model-live.json` và `artifacts/langfuse-proof.json` là bằng chứng local bị Git bỏ qua; báo cáo public chỉ ghi metrics và dữ liệu tổng hợp đã duyệt.
