# ChatSAR

ChatSAR là MVP hỏi đáp dữ liệu bằng tiếng Việt, có kết quả có kiểu và nguồn đối
chiếu. Hiện có CSV/XLSX → tự chuẩn bị → preview trước/sau → Save → hỏi SQL một
bảng, chat/history và SQL thực theo từng message; backend dùng một QueryRequest
→ QueryPlan/binder/compiler SQLAlchemy Core → PostgreSQL chỉ đọc.

**Trạng thái hiện hành:** Giai đoạn 1 **PHASE_1_TECHNICALLY_ACCEPTED** trong
phạm vi single-table đã thống nhất ngày01/11/2026. Giữ nguyên giới
hạn/điểm/rawFAIL;26NL gốc và12reg bổ sung vẫn NOT_RUN, không tuyên bố đã chạy
đủ90 hay mọi câu đều đúng. Chi tiết [PREFLIGHT](docs/PREFLIGHT.md). PR#1 vẫn
Draft, chưa merge.

**Giai đoạn 2: PLANNED / PENDING OWNER APPROVAL.** Kế hoạch đã cập nhật theo yêu
cầu05/11; chưa có code JOIN/RAG/embedding/reranker/parser/worker/UI mới. Đọc
[Implementation Plan mục17](docs/IMPLIMENT_PLAN.md#17-phase-2--automatic-relationships-document-ingestion-rag--unified-chat):

- R0: readiness, nghiên cứu, hợp đồng và benchmark độc lập trước coding.
- R1: tự tìm quan hệ, backend kiểm toàn dữ liệu và semantic/grain evidence rồi
  auto-approval; không yêu cầu user chọn/duyệt PK/FK. Thiếu bằng chứng thì không
  JOIN, single-table tiếp tục.
- R2: document ingestion, parser/license benchmark, durable jobs và chọn
  embedding bằng đo.
- R3: so dense/dense+lexical/dense+lexical+BGE, grounded answers/citations, một
  production retrieval path.
- R4: unified chat, tự chọn năng lực/provider trong quyền, nguồn và follow-up
  đáng tin.

Hybrid SQL+tài liệu/policy evaluator giữ ở Giai đoạn3. Zero-config không là
quyền gửi private documents sang cloud. Cấu hình, khả dụng, quyền dữ liệu và
budget được kiểm riêng;36Gemini manual cũ không là ngân sách Giai đoạn2. Nhiệm
vụ cleanup/plan không sử dụng cloud credits mới.

Kiến trúc hiện hữu: React/TypeScript/Vite + FastAPI/Pydantic +
PostgreSQL/pgvector + SQLAlchemy Core, một Compose project `chatsar`. Web local
`http://localhost:18181`; API `http://127.0.0.1:18081`.
[OPERATIONS](docs/OPERATIONS.md) ghi lệnh kiểm thử/vận hành và quy tắc giữ
DB/uploads/ledger/volumes. Không restart/dọn tài nguyên ShopQuery AI, Langfuse
hoặc dự án khác.

## Tài liệu và cách làm việc

- [Quy tắc dự án — đủ 15 nhóm](Skills/Rules.md)
- [Chỉ dẫn Codex cho mỗi phiên](AGENTS.md)
- [Master Plan](docs/ChatSAR_MASTER_PLAN.md)
- [Implementation Plan](docs/IMPLIMENT_PLAN.md)

Giữ nguyên tên hai file kế hoạch hiện có. Tên file cũ được nhắc bên trong tài
liệu không yêu cầu tạo thêm bản sao.

Codex phải đọc Rules và kế hoạch liên quan trước khi thay đổi. Trước lần sửa mã
nguồn đầu tiên, đọc toàn bộ Implementation Plan. Codex được giao quản lý
Git/GitHub theo RULE 09; thay đổi lớn cần nhánh riêng và người dùng phê duyệt
hợp nhất. Mọi thay đổi phải được kiểm tra phù hợp trước khi commit/push lên
`main` hoặc nhánh công việc.

Repository [MinhHoang1403/ChatSAR](https://github.com/MinhHoang1403/ChatSAR) là
**Public**: không commit secrets, dữ liệu nội bộ, tài liệu người dùng, model
weights, database dumps hoặc logs nhạy cảm. `.gitignore` hỗ trợ loại trừ file
local; vẫn phải kiểm tra phần thay đổi đã chọn để commit. Khi cần cấu hình, dùng
`.env.example` chỉ chứa placeholder.
