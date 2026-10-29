# ChatSAR

ChatSAR là MVP demo hỏi đáp dữ liệu bằng tiếng Việt, hướng đến kết quả chính xác, có nguồn đối chiếu và dễ bảo trì:

- **Text-to-SQL:** hỏi dữ liệu CSV/XLSX; backend kiểm tra kế hoạch truy vấn có kiểu và biên dịch truy vấn chỉ đọc bằng SQLAlchemy Core.
- **RAG:** tìm nội dung trong PDF/DOCX/TXT/Markdown rồi trả lời kèm trích dẫn nguồn.
- **Hybrid:** kết hợp số liệu SQL với tài liệu giải thích hoặc đánh giá quy tắc ngưỡng đơn giản.

**Trạng thái:** Đang lập kế hoạch, chưa có mã nguồn ứng dụng hoặc hệ thống để chạy. Thiết lập repository không phải phê duyệt bắt đầu triển khai. Các thông số và ngưỡng trong kế hoạch là đề xuất, chưa phải kết quả kiểm thử.

## Thiết kế dự kiến

Kiến trúc một ứng dụng chia module: React/TypeScript/Vite, FastAPI/Pydantic, PostgreSQL/pgvector, SQLAlchemy Core và Docker Compose. Kế hoạch có Google Login, Gemini/Knowledge, BGE reranker chạy local, LlamaParse có điều kiện và Langfuse project riêng. Tính tương thích và phiên bản phải được xác minh khi được giao triển khai.

Ưu tiên giải pháp đơn giản nhất đáp ứng MVP; không tự mở rộng công nghệ. Cloud trả phí mặc định tắt, ngân sách bằng 0 đến khi được người dùng phê duyệt. ChatSAR độc lập với ShopQuery AI; không sửa source, dữ liệu hay dịch vụ của dự án khác.

## Tài liệu và cách làm việc

- [Quy tắc dự án — đủ 15 nhóm](Skills/Rules.md)
- [Chỉ dẫn Codex cho mỗi phiên](AGENTS.md)
- [Master Plan](docs/ChatSAR_MASTER_PLAN.md)
- [Implementation Plan](docs/IMPLIMENT_PLAN.md)

Giữ nguyên tên hai file kế hoạch hiện có. Tên file cũ được nhắc bên trong tài liệu không yêu cầu tạo thêm bản sao.

Codex phải đọc Rules và kế hoạch liên quan trước khi thay đổi. Trước lần sửa mã nguồn đầu tiên, đọc toàn bộ Implementation Plan. Codex được giao quản lý Git/GitHub theo RULE 09; thay đổi lớn cần nhánh riêng và người dùng phê duyệt hợp nhất. Mọi thay đổi phải được kiểm tra phù hợp trước khi commit/push lên `main` hoặc nhánh công việc.

Repository [MinhHoang1403/ChatSAR](https://github.com/MinhHoang1403/ChatSAR) là **Public**: không commit secrets, dữ liệu nội bộ, tài liệu người dùng, model weights, database dumps hoặc logs nhạy cảm. `.gitignore` hỗ trợ loại trừ file local; vẫn phải kiểm tra phần thay đổi đã chọn để commit. Khi cần cấu hình, dùng `.env.example` chỉ chứa placeholder.
