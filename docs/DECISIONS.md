# Quyết định và kiểm tra tiền triển khai ChatSAR

Ngày: 29/10/2026. Baseline: `c05f26b1a301e91e8ea6ddaadedb0e1ed03b735d`.
Người cấp quyền: chủ dự án, yêu cầu bắt đầu preflight và Giai đoạn 1 trong hội thoại.

## Phạm vi và trạng thái gate

- Được triển khai theo kế hoạch F1 → F2 → F3 → F4, trên `feature/sql-foundation`; chưa được merge hoặc sang Giai đoạn 2.
- Yêu cầu mới thay thế giới hạn chỉ thiết lập GitHub trước đây. Không làm lại phần GitHub đã hoàn thành.
- **Design review:** baseline hợp đồng/ownership/layout/benchmark đã cụ thể hóa theo kế hoạch. Chỉ đạo mới cho phép hoàn thiện F1 rồi F2 và phần độc lập F3/F4 qua test harness dù Google live BLOCKED. Nghiệm thu live và Phase 1 tổng thể vẫn cần bằng chứng; không giả PASS.
- Theo chỉ đạo tiếp tục phần độc lập khi thiếu điều kiện bên ngoài, được chuẩn bị hợp đồng, oracle/fixtures và nền tảng F1 không gọi provider. Đây không phải nghiệm thu đầy đủ Giai đoạn 1; chỉ chuyển milestone khi acceptance tương ứng thực sự đạt.
- Không đổi kiến trúc đã chọn. Các quyết định chi tiết dưới đây là cụ thể hóa kế hoạch, không phải kết quả phần mềm đã chạy. Kết quả đo được ghi tại `PREFLIGHT.md`.

## Các quyết định nền tảng

| Quyết định | Lựa chọn dùng | Hai phương án không chọn | Căn cứ, chi phí/rủi ro và kiểm thử |
|---|---|---|---|
| Kiến trúc | React/TypeScript/Vite + FastAPI/Pydantic + SQLAlchemy Core + PostgreSQL/pgvector, một Compose | Microservices; thêm DB/agent framework | Đúng kế hoạch; một pipeline SQL; kiểm tra tích hợp thật |
| Ownership | Một owner/workspace; principal và catalog binding do server quyết định | Tin owner từ client; dựa hoàn toàn vào quyền SELECT chung | Reader dùng chung không tự cô lập tenant; bắt buộc negative tests ở API trước nghiệm thu |
| Dữ liệu vật lý | Schema `data`, bảng revision với identifier do server sinh; metadata trong `app` | Tên bảng từ filename; schema-per-user | Cần POC PostgreSQL về quyền, transaction rollback và publish trước F3 |
| DB roles | Admin/migration riêng; app writer; reader SELECT không owner/superuser/BYPASSRLS | API chạy superuser; LLM chọn role/schema | App không nhận mật khẩu admin. Reader có timeout và transaction chỉ đọc; tests quyền thực |
| SQL | LLM chỉ đề xuất typed plan; server bind rồi SQLAlchemy Core compile | Thực thi raw SQL model; nhiều generator/fallback | Strict structure không chứng minh hiểu đúng câu hỏi; oracle độc lập là bắt buộc |
| Literal/kiểu | Giữ raw phrase + typed value + provenance; Decimal, TEXT ID, NULL rõ | Ép float; tự chuẩn hóa giá trị mơ hồ | Cases quận 3/3, 0007/7, COUNT và precision |
| Google | Web Client ChatSAR riêng, GIS POST + double-submit CSRF, session DB | Dùng client/session ShopQuery; email làm khóa | Backend verify chữ ký/iss/aud/exp/sub; live login cần cấu hình thực |
| Cloud | OFF mặc định; chỉ bật theo quyền/hạn mức người dùng điền; không fallback ngầm, chỉ synthetic | Suy ra free tier; tự chọn ngân sách dương | Chủ dự án đã cấp smoke tests; cấu hình hiện tại 10 requests tổng và 10 USD, thấp hơn mức 10/provider; kết quả ở PREFLIGHT |
| Benchmark | SQL oracle viết tay + expected cố định + đối chứng Decimal; tách development/regression/held-out | Sinh gold bằng compiler; sửa expected theo model | Khóa checksum trước compiler/tuning. Held-out bị dùng để sửa phải chuyển sang regression |
| Hạ tầng | Một Compose project `chatsar`; tài nguyên/volumes riêng; bind localhost | Copy source/test stack; tái sử dụng DB/volume dự án khác | Kiểm tra ports cả container đang dừng; không restart/dọn dịch vụ khác |

Các chi tiết trên do Codex đề xuất trong phạm vi kế hoạch được chủ dự án cho triển khai ngày 29/10/2026; không ghi nhận có một lần phê duyệt riêng từng chi tiết hoặc benchmark threshold.

F4 cụ thể hóa bằng một QueryPlan/binder/compiler, một adapter lựa chọn provider mỗi lượt và read-only reader engine. Các biện pháp coverage chỉ là guard nội bộ; oracle/gold độc lập mới dùng để chấm nghĩa. Schema provider được chiếu bỏ maxItems lồng nhau và yêu cầu properties đầy đủ theo giới hạn constrained decoding chính thức; server giữ nguyên caps. Kiểm thử HTTP giả lập phát hiện SDK 2.34.0 đổi attempts=0 thành 1 rồi bridge Interactions hiểu là retry: thêm chốt một HTTP dispatch trong client mỗi reservation, không sửa dependency/vendor SDK và không gọi live thêm để thử.

## Điều kiện bên ngoài và phạm vi bị chặn

| Điều kiện | Trạng thái trước triển khai | Tác động |
|---|---|---|
| Google OAuth Client/origin riêng | Chủ dự án đang tạo, chưa có cấu hình local để xác minh | Real Google E2E và nghiệm thu đầy đủ F2 BLOCKED |
| Knowledge base URL/protocol/auth/allowlist | Chủ dự án có URL; chưa cung cấp file local; không giả định OpenAI-compatible | Probe từ container và model-live BLOCKED |
| Langfuse project/keys ChatSAR | Chủ dự án đang tạo; server hiện hữu đang dừng | Không restart server; tracing live BLOCKED, không chặn health nền tảng |
| Gemini model+SDK+schema live | Tài liệu có model; account access chưa thử; budget 0 | Model-live BLOCKED, không đổi model |
| LlamaParse/embedding/BGE inference | Chưa benchmark; không thuộc triển khai Phase 1 | Chỉ inventory; không tải model/triển khai Phase 2 |
| Ngưỡng latency và chất lượng | Theo §19 là đề xuất; chưa có baseline và phê duyệt riêng | Báo số đo, không tự công bố release PASS |

## Nguồn đã đối chiếu

- PostgreSQL privileges: https://www.postgresql.org/docs/17/ddl-priv.html
- SQLAlchemy Core SELECT: https://docs.sqlalchemy.org/en/20/core/selectable.html
- Pydantic strict validation: https://docs.pydantic.dev/latest/concepts/strict_mode/
- Google ID token/CSRF: https://developers.google.com/identity/gsi/web/guides/verify-google-id-token
- Google-auth clock_skew_in_seconds (10 giây là lựa chọn nội bộ đã kiểm thử, không phải khuyến nghị mặc định của Google): https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.id_token.html
- Docker health dependencies: https://docs.docker.com/compose/how-tos/startup-order/
- Gemini model (không chứng minh account access): https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite
- Langfuse compatibility: https://langfuse.com/self-hosting/upgrade/versioning
- Gemini JSON Schema và giới hạn grammar: https://ai.google.dev/gemini-api/docs/structured-output
- Gemini Interactions/store/continuation: https://ai.google.dev/gemini-api/docs/interactions-overview
- Gemini pricing dùng để ước tính, không phải hóa đơn: https://ai.google.dev/gemini-api/docs/pricing
- Langfuse Observations API v2: https://langfuse.com/docs/api-and-data-platform/features/public-api
- PostgreSQL aggregate return types: https://www.postgresql.org/docs/17/functions-aggregate.html

Nguồn xác nhận cơ chế; lựa chọn lưu trữ, giới hạn và oracle là thiết kế nội bộ cần kiểm thử. Không lấy tài liệu làm bằng chứng runtime PASS.
