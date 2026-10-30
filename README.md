# ChatSAR

ChatSAR là MVP demo hỏi đáp dữ liệu bằng tiếng Việt, hướng đến kết quả chính xác, có nguồn đối chiếu và dễ bảo trì:

- **Text-to-SQL:** hỏi dữ liệu CSV/XLSX; backend kiểm tra kế hoạch truy vấn có kiểu và biên dịch truy vấn chỉ đọc bằng SQLAlchemy Core.
- **RAG:** tìm nội dung trong PDF/DOCX/TXT/Markdown rồi trả lời kèm trích dẫn nguồn.
- **Hybrid:** kết hợp số liệu SQL với tài liệu giải thích hoặc đánh giá quy tắc ngưỡng đơn giản.

**Trạng thái: NOT_ACCEPTED — chưa qua Giai đoạn 2.** Giai đoạn 1 trên `feature/sql-foundation` có Google/workspaces, CSV/XLSX/Smart Setup, catalog, QueryRequest → QueryPlan/compiler SQLAlchemy Core, chat/history, câu trả lời tất định và SQL thật theo từng lượt. Nguồn private ready có cấp/thu hồi quyền riêng từng provider; usage review giữ dự phòng có audit, không sửa chi phí chưa biết. Giao diện sáng xanh dương, workspace context ở header, hai nút Nguồn & xử lý / Truy vấn SQL.

Kiểm hiện hành:148unit/34integration/25oracle/75gold+5replacement/25evaluation/12frontend PASS; browser30checks PASS/2BLOCKED (Google mới/hai tài khoản). Cùng26ca model baseline cải thiện22→26PASS; tập mở rộng tổng39ca35PASS/4FAIL, in-scope27/31, còn57/90ca gốc chưa đo. SQL/provenance/restart đã kiểm qua browser/Gemini thật. Không coi tests offline là model accuracy hoặc tự nghiệm thu. Xem [bằng chứng, chi phí và lỗi còn lại](docs/PREFLIGHT.md). PR#1 còn Draft, chưa merge; RAG/Hybrid chưa triển khai.

## Thiết kế dự kiến

Kiến trúc một ứng dụng chia module: React/TypeScript/Vite, FastAPI/Pydantic, PostgreSQL/pgvector, SQLAlchemy Core và Docker Compose. Kế hoạch có Google Login, Gemini/Knowledge, BGE reranker chạy local, LlamaParse có điều kiện và Langfuse project riêng. Tính tương thích và phiên bản phải được xác minh khi được giao triển khai.

Ưu tiên giải pháp đơn giản nhất đáp ứng MVP; không tự mở rộng công nghệ. Cấu hình provider local được giữ nguyên; quyền gọi và hạn mức được kiểm tra riêng. Chủ dự án cho phép smoke tests Gemini/Knowledge có giới hạn, luôn áp dụng giới hạn cấu hình thấp hơn. ChatSAR độc lập với ShopQuery AI; không sửa source, dữ liệu hay dịch vụ của dự án khác.

Web local: `http://localhost:18181`; hướng dẫn chạy và kiểm thử tại [OPERATIONS.md](docs/OPERATIONS.md). Chỉ có một Compose project `chatsar`, không cần bản sao source/test stack.

## Tài liệu và cách làm việc

- [Quy tắc dự án — đủ 15 nhóm](Skills/Rules.md)
- [Chỉ dẫn Codex cho mỗi phiên](AGENTS.md)
- [Master Plan](docs/ChatSAR_MASTER_PLAN.md)
- [Implementation Plan](docs/IMPLIMENT_PLAN.md)

Giữ nguyên tên hai file kế hoạch hiện có. Tên file cũ được nhắc bên trong tài liệu không yêu cầu tạo thêm bản sao.

Codex phải đọc Rules và kế hoạch liên quan trước khi thay đổi. Trước lần sửa mã nguồn đầu tiên, đọc toàn bộ Implementation Plan. Codex được giao quản lý Git/GitHub theo RULE 09; thay đổi lớn cần nhánh riêng và người dùng phê duyệt hợp nhất. Mọi thay đổi phải được kiểm tra phù hợp trước khi commit/push lên `main` hoặc nhánh công việc.

Repository [MinhHoang1403/ChatSAR](https://github.com/MinhHoang1403/ChatSAR) là **Public**: không commit secrets, dữ liệu nội bộ, tài liệu người dùng, model weights, database dumps hoặc logs nhạy cảm. `.gitignore` hỗ trợ loại trừ file local; vẫn phải kiểm tra phần thay đổi đã chọn để commit. Khi cần cấu hình, dùng `.env.example` chỉ chứa placeholder.
