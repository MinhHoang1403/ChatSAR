# ChatSAR

ChatSAR là MVP demo hỏi đáp dữ liệu bằng tiếng Việt, hướng đến kết quả chính xác, có nguồn đối chiếu và dễ bảo trì:

- **Text-to-SQL:** hỏi dữ liệu CSV/XLSX; backend kiểm tra kế hoạch truy vấn có kiểu và biên dịch truy vấn chỉ đọc bằng SQLAlchemy Core.
- **RAG:** tìm nội dung trong PDF/DOCX/TXT/Markdown rồi trả lời kèm trích dẫn nguồn.
- **Hybrid:** kết hợp số liệu SQL với tài liệu giải thích hoặc đánh giá quy tắc ngưỡng đơn giản.

**Trạng thái: PARTIALLY_READY.** Giai đoạn 1 trên `feature/sql-foundation` có Google/workspaces, CSV/XLSX, Smart Data Setup (local hoặc AI metadata có consent), catalog nghiệp vụ, SQL một bảng, chat/history/source và giao diện sáng xanh dương. Kết quả bị cắt được báo rõ; Decimal/NULL/TEXT ID được giữ nguyên. Gemini mặc định, Knowledge dự phòng theo opt-in/quyền dữ liệu/kết nối/hạn mức.

94 unit, 24 integration, 25 SQL oracle gốc, 13 manifest/quyền DB, 75 phép kiểm gold SQL của bộ 90 tình huống và 7 frontend SSR/DTO đã PASS local. Đây không phải accuracy model. Model-live của bản cải tiến cần quyền bổ sung; browser sau đăng nhập bị chặn bởi công cụ Cốc Cốc. Google live trước đó đã có bằng chứng thủ công + DB. Chưa nghiệm thu cuối, chưa merge main; RAG/Hybrid chưa triển khai. Xem [bằng chứng và blockers](docs/PREFLIGHT.md).

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
