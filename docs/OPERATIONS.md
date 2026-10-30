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
foreach ($name in @('foundation','identity','datasets','conversation','catalog')) {
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
py -3.11 -m evaluations.semantic
py -3.11 -m evaluations.planning
py -3.11 -m evaluations.acceptance  # chỉ prepare; không gọi model
py -3.11 -m evaluations.runtime
py -3.11 -m evaluations.integration
py -3.11 -m evaluations.model_live --providers gemini --cases logistics_sum hotel_sum library_sum --prepare-only
py -3.11 -m evaluations.persistence

# Kiểm tra code trong backend: uv run --frozen ruff check app tests
# Format: uv run --frozen ruff format --check app tests
# Types: uv run --frozen mypy
# Unit: uv run --frozen pytest -q
# Frontend: npm.cmd run typecheck; npm.cmd run build (trong frontend/)
# Frontend SSR/DTO: npm.cmd test --prefix frontend (không phải browser E2E)

# Dừng đúng ChatSAR khi cần, giữ nguyên volume.
docker compose stop
```

Không chạy `down -v`, prune volumes, restart dịch vụ khác hoặc dùng rollback Git thay backup dữ liệu. Bootstrap roles chỉ chạy với volume mới; thay mật khẩu trong `.env` sau khi DB đã tạo không tự đổi mật khẩu DB. Migration dùng role admin trong DB service; API chỉ nhận app credential. Không truyền admin URL vào API container.

Các bước backup/restore đầy đủ chưa được nghiệm thu ở F1; phải bổ sung theo milestone có dữ liệu người dùng trước khi tuyên bố release an toàn. Hiện các bảng benchmark được nạp trong transaction rồi rollback; tests quyền chỉ tạo/xóa đúng bảng tổng hợp có ID ngẫu nhiên của lần chạy.

## Chat, cloud và tracing

Luồng review mới: Quản lý dữ liệu → tải file → chọn sheet → Phân tích local hoặc cấp quyền metadata cho lượt AI → xem đề xuất → Chỉnh sửa chi tiết nếu cần → cấp quyền gửi metadata/câu hỏi cho từng provider nếu muốn chat nguồn private → Xác nhận và sử dụng dữ liệu → đóng hộp thoại → chọn nguồn ở header → gửi câu hỏi. Gemini mặc định. Nguồn private vẫn private khi cấp quyền chia sẻ; quyền setup một lượt không tự cho phép gửi query tới Gemini/Knowledge. Không cần chọn synthetic cho dữ liệu thật. Nếu AI lỗi, dùng local review, kiểm ô trống/ngày/đơn vị rồi xác nhận. Không tự sửa .env.

Migration catalog là additive, không tạo bảng dữ liệu thay thế; rollback ứng dụng giữ cột mới và không DROP. Ready revision cũ vẫn đọc được với defaults, không cần reupload hoặc sửa file nguồn. Kết quả partial không dùng làm premise follow-up. Fallback cần opt-in theo request và bằng chứng Knowledge từng truy cập được; 403 gần nhất chặn fallback tự động. Timeout không tự gọi lại provider khác.

`evaluations.acceptance --live --max-requests 3 --expected-ledger 12` là lệnh của lần nghiệm thu đã được duyệt ngày 30/10: đã dùng một lượt rồi dừng vì SETUP_PROPOSAL_REJECTED. Ledger hiện 13 (Gemini 8/Knowledge 5); không chạy lại lệnh này hoặc tự dùng hai lượt còn lại sau điều kiện dừng. Dừng khi setup/provider/answer không đạt, không retry/Knowledge. Không reset ledger hoặc tăng cap 10/provider. Prepare-only có thể chạy không cần quyền generation và đối chiếu toàn bộ typed rows/checksum, sau đó dọn đúng test owner. Hạn mức .env không thay cho quyền tác vụ.

Sau Google login: tạo/chọn workspace → tải CSV/XLSX → review kiểu/NULL/timezone → xác nhận → mở bộ dữ liệu ready → chọn mô hình và gửi câu hỏi. Dữ liệu private chỉ được gửi metadata/câu hỏi tới đúng provider có quyền sharing_providers; chỉ chọn synthetic cho dữ liệu thực sự tổng hợp. Khi đổi nguồn của conversation đã có câu trả lời, tạo conversation mới. Lịch sử và kết quả được lưu trong PostgreSQL; không dùng localStorage để lưu session.

Origin browser phải trùng `APP_ORIGIN`: `localhost` và `127.0.0.1` là hai origin khác nhau. Giao diện đọc origin chuẩn từ `/api/auth/config` rồi chuyển về đó trước khi khởi tạo Google Login. Không nới allowlist/CSRF để chấp nhận tùy ý các origin. Sau đổi cấu hình local cần `docker compose up -d --wait` để container nạp lại; không build lại image chỉ vì đổi `.env`.

`evaluations.model_live --prepare-only` chỉ kiểm fidelity dữ liệu qua HTTP, không gọi model. Bỏ cờ này sẽ gọi provider thật: chỉ được chạy khi có hạn mức còn lại và quyền rõ ràng. Không chạy lệnh live để kiểm health. Mốc trước quyền bổ sung 30/10 có 12 reservations; hiện 13 sau một lượt AI Setup bị từ chối. `.env` do chủ dự án đặt max 20/budget 20 USD không cấp quyền Codex tự gọi thêm. Không xóa ledger/reset bộ đếm/tăng cấu hình để chạy thêm. Hai lượt còn lại của kế hoạch ba lượt chưa dùng do đã dừng sau FAIL. Lỗi và timeout vẫn tính reservation; số HTTP request lịch sử trước khi sửa SDK guard chưa được xác minh đầy đủ, xem PREFLIGHT.

Provider timeout hiện 60 giây; nginx proxy đọc và HTTP harness chờ 90 giây để không cắt trước provider. Mức 60 giây được đặt sau ca hotel timeout ở 30 giây, chưa xác minh live lại trong hạn mức hiện tại. Timeout không bảo đảm request phía provider đã bị hủy hoặc không bị tính phí; không tự gửi lại cùng câu hỏi khi chưa đọc lại trạng thái/lịch sử.

Langfuse dùng server hiện hữu; API container tự đổi localhost thành host.docker.internal chỉ trong bộ nhớ. Không sửa `.env`, không tạo service mới. SDK 5 dùng OTEL ingestion và Observations API v2; `/api/public/traces` cũ có thể trả 404. Chẩn đoán chỉ đọc field metadata do ChatSAR đặt, không in metadata SDK toàn bộ vì có thể chứa public key. `artifacts/model-live.json` và `artifacts/langfuse-proof.json` là bằng chứng local bị Git bỏ qua; báo cáo public chỉ ghi metrics và dữ liệu tổng hợp đã duyệt.
