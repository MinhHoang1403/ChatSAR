# Hợp đồng Phase 1 trước khi lập trình

Baseline theo Implementation Plan §3, §5–7, §12, §16. Chỉ các endpoint thuộc milestone đã triển khai mới được công bố hoạt động. JSON dùng UTF-8; UUID được server kiểm tra; datetime ISO 8601 kèm timezone; giá trị NUMERIC trên wire là chuỗi thập phân, NULL là `null`, TEXT ID giữ zero đầu.

## Ranh giới tin cậy

`principal`, `owner_id`, `workspace_id` được cấp quyền, `source_revision`, physical identifiers, role và quyền đọc do server/catalog quyết định. Client chỉ gửi ID tham chiếu; luôn kiểm tra quyền trước lookup/query và khi đọc lại kết quả. Proposal không được chứa owner, SQL, schema, DB role, canonical verified flag hoặc tên bảng vật lý. Trường dư bị từ chối, không tự bỏ qua.

Mỗi literal phải giữ `raw_phrase`, `value_type`, `candidate_value`, và sau binding có `canonical_value`, `mapping_source`, `question_span`. Không tự đổi `quận 3` thành `3`, `0007` thành số, tháng thiếu năm thành năm hiện tại. Nếu thiếu ngữ cảnh quan trọng: `clarify`. Không có schema alias/mapping thì không tự bịa.

## Wire API

| Endpoint | Request | Response và bảo vệ |
|---|---|---|
| GET `/live` | Không auth | 200 `{status:"ok",request_id}`; không gọi DB/provider |
| GET `/ready` | Không auth | 200/503 `{status:"ok" hoặc "unavailable",request_id}`; DB + version migration đúng |
| GET `/health` | Không auth | Readiness + cờ `cloud_calls_allowed` boolean; không trả URL/key/exception; không gọi model |
| GET `/api/auth/config` | Không auth | Client ID công khai nếu có, `app_origin`, nonce/CSRF; challenge cookie có chữ ký, HttpOnly, TTL 10 phút; no-store |
| POST `/api/auth/google` | GIS JS callback gửi JSON `credential`, `g_csrf_token`; challenge cookie gắn nonce/CSRF | Verify CSRF trước token, chữ ký/iss/aud/exp/sub/nonce; nonce single-use trong DB; rotate session; HttpOnly cookie; không trả Google token |
| POST `/api/auth/logout` | Session cookie + `X-CSRF-Token` | Revoke DB session, clear cookie; 204 |
| GET `/api/me` | Session cookie | `{id,display_name,csrf_token}`; không email làm khóa; unauth 401 |
| GET/POST `/api/workspaces` | POST `{name}` + CSRF | List owner-scoped; create 201 `{id,name}` |
| GET `/api/workspaces/{id}` | Session cookie | Select workspace đã kiểm owner; ngoài quyền trả 404 |
| POST `/api/workspaces/{id}/datasets` | Multipart `file`, optional `sheet_name` + CSRF | 202 `{dataset_id,revision_id,job_id,status}`; kiểm owner trước đọc bytes; dedupe theo workspace/checksum |
| GET `/api/workspaces/{id}/datasets` | Session | List catalog của workspace sau owner check |
| GET `/api/datasets/{id}/preview` | `revision_id`, `offset`, `limit` | Columns + candidate types/rows/warnings; owner + revision checked |
| POST `/api/datasets/{id}/confirm` | `{revision_id,columns,sheet_name,grain,timezone,data_classification}` + CSRF; unit trong từng column | Atomic publish; 200 `{revision_id,status:"ready",row_count,checksum}`; lỗi row-level không bỏ hàng |
| GET `/api/jobs/{id}` | Session | Trạng thái durable + lỗi công khai đã lọc; 404 cho object không thuộc owner |
| GET/POST `/api/conversations` | POST `{workspace_id,title}` + CSRF | Owner-scoped IDs; không nhận owner từ client |
| GET `/api/conversations/{id}` | Session | Messages/result refs đã kiểm owner và source revision |
| POST `/api/conversations/{id}/messages` | `{question,dataset_revision_id,provider}` + `Idempotency-Key` + CSRF; provider gemini/knowledge | AnswerEnvelope; không cho client gửi GroundedQuery/SQL vào production API |
| GET `/api/results/{id}` | Session | Stored envelope + revision provenance; kiểm owner lại |

Lỗi: `{error:{code,message},request_id}`. 400/422 malformed/validation, 401 unauth, 403 CSRF, 404 object không tồn tại hoặc ngoài owner, 409 stale revision/idempotency conflict, 413 upload cap, 503 dependency unavailable. Không trả traceback, SQL lỗi, provider body hoặc secrets. Các endpoint tài liệu/RAG thuộc Phase 2, không được giả hoạt động.

Cookie session: random opaque token ≥32 bytes, chỉ lưu hash trong DB, TTL ứng viên 24 giờ, revoke khi logout/rotation. `HttpOnly`, `SameSite=Lax`, `Secure` trên HTTPS; local HTTP chỉ localhost và được ghi rõ chế độ development. State-changing routes yêu cầu token CSRF gắn session và same-origin. Không dùng token tự tạo ở frontend thay Google login trong runtime; dependency override chỉ dành cho test.

## Typed query và execution

Model proposal: `task`, `table_id`, `source_revision_id`, `raw_user_spans`, `select_columns`, `aggregations`, `filters`, `group_by`, `order_by`, `limit`, `unresolved`. `task` có SQL/CLARIFY/UNSUPPORTED trong Phase 1. Strict enums, số lượng/depth caps; unknown fields/operators/tables bị từ chối.

Proposal bổ sung `intent`, `entities`, `metric`, `population`, `coverage` để giữ dấu vết ý định. `raw_user_spans` phải là các đoạn nguyên văn bao phủ câu hiện tại; `coverage` sao chép đúng các span đã biểu diễn, còn thiếu thì CLARIFY. Entity đã khai báo phải có literal filter tương ứng. Đây là kiểm tra nhất quán và các qualifier đã biết, không phải semantic oracle: model có thể khai thiếu/sai qualifier; vẫn phải chấm trên gold độc lập. Mỗi literal dùng `candidate_value` dạng chuỗi có kiểu, không nhận expression.

Schema constrained decoding bỏ `maxItems` lồng đệ quy để tránh bùng nổ grammar; mọi cap gốc vẫn được Pydantic/server kiểm tra. Schema gửi model yêu cầu đầy đủ các properties để tránh proposal rỗng do optional defaults. Cùng một contract được đưa vào prompt vì Knowledge không bảo đảm thực thi `response_format`.

Ngày chỉ bind từ ISO hoặc format catalog đã xác nhận, timestamp dùng timezone đã duyệt. Khoảng tháng cần suy đầu/cuối tháng từ ngôn ngữ chưa được tự chuyển; dùng clarify. Không tự đoán năm. SUM trên BIGINT của PostgreSQL trả NUMERIC; wire là chuỗi giống SUM/AVG Decimal. Số nguyên ngoài khoảng an toàn JavaScript được chuyển thành chuỗi để giữ chính xác.

Filter leaf: `{column_id,operator,literal}`; AND/OR node: `{operator,children}`. NULL chỉ dùng IS_NULL/IS_NOT_NULL. IN có danh sách typed literals bị cap. Aggregate: `{operator,column_id,output_id}`; COUNT_ROWS không có column; các loại khác bắt buộc column phù hợp. Order chỉ tham chiếu selection/aggregate ID hợp lệ, không có expression string. Server khóa `limit` 1–500.

Sau binding, `GroundedQuery` chứa server-owned table/column objects, workspace/revision, typed literals + provenance, metric/unit/grain, filters/group/order/limit. Compiler chỉ nhận đối tượng đã bind, không nhận raw SQL hoặc identifier do người dùng tùy ý chọn. Kiểm G1–G8 theo kế hoạch; không tuyên bố qualifier coverage do model tự báo là chứng minh semantic correctness.

Reader connection riêng: không superuser/owner/BYPASSRLS, không DDL/DML, không CREATE/TEMP database. Dùng read-only transaction, statement_timeout và row cap. Role chung có SELECT trên published data không tự đảm bảo tenant isolation: API và catalog allowlist là tuyến bắt buộc. Query errors không được đổi thành rows/facts giả. Không dùng EXPLAIN ANALYZE làm preflight.

## Kết quả và lịch sử

`AnswerEnvelope`: `{status,facts,display_rows,citations,limitations,display_text,request_id}`.
Status: answered/partial/insufficient/clarify/unsupported/provider_unavailable/execution_error. `facts` có typed columns/rows, metric/unit/filters/timezone, source revision/checksum, execution ID. SQL citation là tham chiếu dataset/revision/result đã cấp quyền; Decimal vẫn là chuỗi, NULL không thành 0.

`verified_result` chỉ khi execution và kiểm tra bằng chứng cần thiết đạt; partial/error/unsupported không được nâng trust. Follow-up không lấy assistant prose làm fact. Source revision thay đổi phải báo stale hoặc re-run rõ ràng; không tự dùng revision mới thay số liệu cũ.

Envelope lưu kết quả thực, `result_id` khi answered và `trace_id` nếu tracing hoạt động; không ghi raw SQL vào presentation. Follow-up chỉ lấy question + typed plan của lượt answered gần nhất cùng revision. Đổi revision trong conversation đã có kết quả trả 409 STALE_CONTEXT và yêu cầu conversation mới. Retry cùng key/body đọc lại envelope cũ; key khác body trả 409; pending không sinh lại model. Restart chuyển pending thành execution_error có thể đọc lại; muốn thử lại cần yêu cầu mới.

Provider chỉ được đọc metadata của nguồn do owner xác nhận synthetic; private bị chặn trước reserve/network. Hạn mức request/cost được reserve bằng transaction + advisory lock, gồm cả lượt thất bại. Không fallback. HTTP client chặn lần dispatch thứ hai trong cùng reservation, kể cả SDK tự retry. Tracing chỉ gửi metadata/status/row count, không gửi question/raw rows/secret mặc định; facts đầy đủ giữ trong PostgreSQL đã kiểm owner.

Các ví dụ/hợp đồng trên là baseline thiết kế nội bộ. Khi hiện thực, xuất OpenAPI từ code và kiểm tra khớp các hợp đồng này; không âm thầm sửa contract để vừa implementation.

Upload hiện dedupe bằng `(workspace_id, source checksum)`; một file có một revision đã chọn sheet trong phạm vi này. GET preview nhận `sheet_name` để xem trước mà không ghi DB; confirm chốt `sheet_name`, `columns`, `timezone`, `grain`, `data_classification`. Mỗi column có `id`, `name`, `data_type`, `nullable`, `primary_key`, `null_values`, `date_format`, `decimal_separator`, `unit`. `null_values=[]` giữ ô trống TEXT; chọn `['']` rõ ràng mới đổi ô trống thành NULL. Published revision bất biến; confirm lần nữa trả 409. Không hỗ trợ chỉnh sửa nguồn/công bố revision khác qua cùng endpoint ở mốc này.
