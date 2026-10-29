# Bằng chứng triển khai Giai đoạn 1

Ngày 29/10/2026. Nhánh `feature/sql-foundation`; main nền `c05f26b1a301e91e8ea6ddaadedb0e1ed03b735d`.

## Quyền và ngoại lệ đã được chủ dự án xác nhận

Tiếp tục F1 → F4 từ mã đang có. Được kiểm thử F3/F4 bằng test harness có kiểm soát dù Google live còn BLOCKED. Không có runtime login bypass. Không merge main, không sang Giai đoạn 2/3.

Giữ nguyên `.env` và flags enabled. Tối đa 10 lời gọi Gemini và 10 Knowledge trong nhiệm vụ, hoặc giới hạn cấu hình thấp hơn. Tại lần kiểm tra đầu, `CLOUD_MAX_REQUESTS=0`, `CLOUD_BUDGET_USD=0`: chưa gọi generation. Enabled không đồng nghĩa có quyền chi tiêu; không tự tăng giới hạn. LlamaParse không được tiêu thụ credits trong Phase 1; BGE không nạp GPU.

## Kiểm kê đã xác minh

| Mục | Bằng chứng | Quyết định/giới hạn |
|---|---|---|
| Host | Windows 11 64-bit; Ryzen 5 7535HS 6C/12T; RAM khoảng 16 GB | Không sửa host/driver |
| Công cụ | Python 3.11.9, uv 0.12.15; Node 24.19.0/npm 11.17.0 | Dependency lockfiles; Docker base images pin digest |
| Docker | Engine 29.7.2, Desktop 4.89.0, Compose 5.5.0 | Một project `chatsar`, db không publish port |
| GPU/cache | RTX 3050 Laptop 6 GB; driver 617.42; BGE snapshot `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` có weights | Chỉ đọc metadata/hash, chưa inference; không tải lại |
| Langfuse | Server/image 4.70.1 hiện hữu, các dịch vụ healthy khi kiểm tra lại | Không restart/update; cấu hình project riêng được người dùng điền local |
| Ports | Web localhost:18181, API 127.0.0.1:18081 | Đã kiểm HTTP thực; một browser origin `http://localhost:18181` |
| Repository | Hai kế hoạch gốc giữ nguyên SHA-256 | Không reset/xóa mã chưa commit |

## F1 — kiểm tra hiện tại

| Kiểm tra | Trạng thái | Bằng chứng |
|---|---|---|
| Backend lint/format/mypy | PASS | `uv run --frozen ruff check app tests`, `ruff format --check`, `mypy` |
| Backend unit | PASS, 10 tests | `uv run --frozen pytest -q`; một cảnh báo deprecation httpx từ thư viện |
| Manifest/Decimal và DB permissions | PASS, 10 tests | `CHATSAR_POSTGRES_TESTS=1 python -m unittest discover -s evaluations/tests -v`; không skip |
| Independent SQL oracle | PASS, 25 cases | `python -m evaluations.oracle`; expected/checksums không đổi |
| Frontend typecheck/build | PASS | `npm run typecheck`, `npm run build` |
| Docker runtime/restart | PASS | web/api/db healthy; `/live`, `/ready`, `/health` HTTP 200 trực tiếp và qua web trước/sau `docker compose restart`; migration còn |
| Browser F1 | PASS thủ công bởi chủ dự án | Người dùng xác nhận trang hiển thị đúng và “Kết nối hệ thống sẵn sàng” trong hội thoại |
| Browser automation | BLOCKED | Công cụ không hỗ trợ URL policy với Cốc Cốc Windows; không gọi đây là automated E2E PASS |
| CI đúng commit đã push | PASS | `b2c692c40f989b8e68ade3e888fed5a74ffa7f3e`, https://github.com/MinhHoang1403/ChatSAR/actions/runs/40850413238 |

Reader thật bị từ chối INSERT/UPDATE/DELETE/DDL/TEMP/đọc metadata; read-only mặc định, timeout 5 giây; Decimal/NULL/TEXT ID đúng. Transaction DDL rollback không để bảng nửa chừng. Đây không phải chứng cứ API owner isolation (thuộc F2/F3).

## Các mốc còn lại

F1 đã đạt các điều kiện nền tảng, browser kiểm tra thủ công do chủ dự án xác nhận; browser automation vẫn BLOCKED độc lập.

F2: đã triển khai users/sessions/workspaces, Google ID-token interface + nonce/CSRF, cookie/session expiry/revoke/rotation và owner guards; frontend login/workspaces shell. 17 backend unit tests PASS; 7 integration tests API với PostgreSQL thật PASS (Google identity chỉ mock trong harness). Không có endpoint đăng nhập test trong runtime. Google live/browser E2E vẫn BLOCKED vì chưa có Client ID. F3/F4 được phép tiếp tục qua harness theo chỉ đạo mới; không gọi toàn bộ F2 PASS.

Gemini/Knowledge live chưa chạy; 8 negative semantic cases đã lưu nhưng chưa chạy qua app. Không dùng oracle-only hoặc mock để báo semantic PASS. Kết quả milestone và CI sẽ cập nhật tại chính file này.

## Google OAuth khi frontend/backend đã xác minh

Frontend chính thức local: `http://localhost:18181`; backend trực tiếp: `http://127.0.0.1:18081`. Browser gọi API qua proxy cùng origin `http://localhost:18181/api`, nên không cần CORS đa origin. Google Identity Services dùng JS callback nhận ID token và POST cùng origin tới `/api/auth/google`, có CSRF cookie/token và nonce. Với chế độ popup callback này không dùng OAuth authorization-code redirect URI. Authorized JavaScript Origin cần khai báo đúng `http://localhost:18181`; không thêm đường dẫn `/api`. Không tạo/sửa OAuth client của ShopQuery.
