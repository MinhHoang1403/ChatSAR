# ChatSAR — IMPLEMENTATION PLAN FOR CODEX

> **Tên file theo yêu cầu:** `Impliment_plan.md`  
> **Ngày lập:** 29/10/2026  
> **Tình trạng:** **IMPLEMENTATION SPECIFICATION — CHƯA ĐƯỢC PHÊ DUYỆT ĐỂ THỰC THI**  
> **Nguồn yêu cầu:** `ChatSAR_PROJECT_HANDOFF(1).md`, `ChatSAR_MASTER_PLAN_2026-10-29.md` và các quyết định trong trao đổi ngày 29/10/2026.  
> **Đối tượng:** Codex triển khai dự án mới **ChatSAR**; chủ dự án dùng để duyệt từng mốc và nghiệm thu.  
> **Ngôn ngữ làm việc:** tiếng Việt, thuật ngữ tiếng Anh giải thích khi cần.  
> **Mục tiêu:** MVP demo chính xác và có thể kiểm chứng cho Text-to-SQL, RAG, Hybrid; **không xây nền tảng doanh nghiệp**.

---

## 0. Cách sử dụng file này và thứ tự ưu tiên

### 0.1. Đọc trước khi làm

**Codex phải đọc toàn bộ file này trước khi sửa bất kỳ mã nguồn nào.** Nếu có hai tài liệu sau trong project, phải đọc thêm:

1. `ChatSAR_PROJECT_HANDOFF(1).md`: định nghĩa mục tiêu, bài học ShopQuery và các điều không được phép lặp lại.
2. `ChatSAR_MASTER_PLAN_2026-10-29.md`: mô tả kiến trúc và phạm vi sản phẩm.
3. File này: nhiệm vụ triển khai, dependency, acceptance, bằng chứng cần báo cáo và cách xử lý bất đồng.

Thứ tự khi có xung đột: **chỉ đạo mới nhất được người dùng xác nhận > nguyên tắc an toàn/bảo mật > hợp đồng và gate đã phê duyệt > file implementation plan > bản master plan/handoff để tham khảo**. Không âm thầm giải quyết bằng cách đổi public contract, mở rộng scope hoặc bỏ kiểm thử. Ghi rõ xung đột và lựa chọn cần duyệt.

### 0.2. Quy tắc tiến hành

- **Đang ở trạng thái lập kế hoạch. Không tự tạo repo, sửa mã, dựng container, chạy smoke test cloud hoặc chi tiêu API** chỉ vì đã có file này.
- Khi chủ dự án ra lệnh bắt đầu giai đoạn/milestone cụ thể: chỉ triển khai đúng phạm vi được giao, dùng kế hoạch làm acceptance contract.
- Trước mọi thao tác có nguy cơ phá hủy, vượt budget, chuyển dữ liệu ra cloud, merge/deploy hoặc chạm dịch vụ đang chạy: phải có quyền rõ ràng; không suy diễn việc “bắt đầu coding” thành quyền thực hiện mọi thao tác.
- ChatSAR là một dự án mới độc lập với **ShopQuery AI**. Không kế thừa mặc định repo, Git history, ports, DB, volumes, sessions, dữ liệu, source, Docker image hoặc secret của ShopQuery. Không xóa/sửa/tắt ShopQuery.
- Có thể **kết nối có quyền** đến Knowledge model host và Langfuse server hiện có; riêng tài khoản/project/credentials của ChatSAR phải tách biệt.
- Không thêm LangChain/LangGraph, Kubernetes, microservices, Redis/Celery, một database thứ hai, LLM gateway, agent tự trị hoặc vector DB riêng khi chưa có bằng chứng và phê duyệt.
- Không tạo nhiều SQL generators/routers/verifiers chạy song song. Không viết regex theo câu hỏi/ngành để qua benchmark. Không hardcode dữ liệu của domain demo vào production.
- **Định nghĩa đầy đủ trước coding, triển khai đường dọc nhỏ, nghiệm thu, rồi mới mở rộng.** Giai đoạn kế hoạch được phép dùng nhãn Phase; tên code/branch/module/runtime không dùng `v1`, `v2`, `s1`, `s2`, `freeze`, `frozen` hay các nhãn giai đoạn tương tự.

### 0.3. Ký hiệu trạng thái bằng chứng

- `PASS`: đã chạy đúng phép thử quy định và có log/evidence.
- `FAIL`: đã chạy và không đạt oracle/acceptance.
- `BLOCKED`: không thể chạy vì điều kiện bên ngoài hoặc thiếu quyền; ghi nguyên nhân.
- `NOT_RUN`: chưa thực hiện; **không** được báo PASS.
- `SKIP`: có lý do hợp lệ, phạm vi và người phê duyệt; không tính thành PASS.
- `UNKNOWN`: chưa đủ thông tin xác định.
- `UPSTREAM_LIMITATION`: nhà cung cấp không hỗ trợ tính năng; phải có dẫn chứng, không suy đoán.

CI xanh, JSON hợp lệ, HTTP 200, SQL chạy được hay citation ID tồn tại **không đồng nghĩa** semantic correctness hoặc user-level acceptance.

### 0.4. Các giá trị là đề xuất, chưa phải số đo

Các thông số như 20 MiB/file, 50.000 rows/sheet, 350–600 tokens/chunk, 20 retrieval candidates, 4–6 evidence chunks, một lần sửa lỗi kỹ thuật, 170 benchmark cases, ngưỡng accuracy đề xuất… là **starting values**. Phải đo, xác nhận và khóa trước held-out/release; không tự coi là kết quả thực nghiệm.

---

## 1. Product contract: cái gì phải chạy và cái gì không phải xây

### 1.1. Kịch bản demo bắt buộc

**Demo SQL:** user đăng nhập → tạo workspace → upload CSV/XLSX → xem preview và xác nhận schema/relationships → hỏi bằng tiếng Việt → có bảng kết quả chính xác và nguồn → hỏi tiếp thay điều kiện.

**Demo RAG:** user upload PDF có text/DOCX/TXT/MD → parse/chunk/embed → truy vấn nội dung → tìm kiếm và BGE rerank → trả lời tiếng Việt kèm nguồn đúng document revision/trang/đoạn → khi thiếu nguồn nói rõ chưa đủ bằng chứng.

**Demo Hybrid:** user hỏi đồng thời về số liệu SQL và tài liệu; hoặc hỏi đối tượng nào đạt/chưa đạt một quy tắc threshold đơn giản → hệ thống xác định rule + scope → SQL lấy facts → evaluator tất định → answer tự nhiên, cho xem cách tính và đoạn chính sách.

**Demo ownership:** hai tài khoản Google khác nhau không xem được workspace, chat, dataset, document, chunk, result và citation của nhau; sau restart/recreate dữ liệu hợp lệ vẫn còn.

### 1.2. Capability matrix

| Nhóm | MVP in-scope | Explicitly out-of-scope |
|---|---|---|
| SQL | SELECT một bảng; filters; COUNT rows/non-null/distinct; SUM/AVG/MIN/MAX; GROUP BY/ORDER BY/LIMIT; typed dates/Decimal; JOIN 2–3 bảng đã xác nhận | SQL tự do, DML/DDL, recursive, window/CTE tùy ý, JOIN suy đoán, 5+ bảng |
| Data | CSV, XLSX có sheet selection, profile/preview, review metadata, immutable publish revision | Tự đồng bộ live ERP/warehouse, mọi schema đều tự hiểu 100% |
| RAG | PDF text, DOCX, TXT/MD; local parser; LlamaParse nếu được phép; vector+lexical; BGE reranker; source citations | OCR scan khó hàng loạt, đọc đồ thị/biểu đồ phức tạp không có oracle |
| Hybrid | SQL facts + explanatory docs; policy threshold đơn giản có unit/time/population/applicability | Luật nhiều ngoại lệ lồng nhau, suy luận pháp lý/nhân quả tùy ý |
| Conversation | Lưu chat, follow-up đổi filter/time, verified result references | Autonomous agents, long-term autonomous memory |
| Accounts | Google Login, mỗi workspace một owner | Roles/multi-org/shared workspace phức tạp |
| Infrastructure | Docker Compose full-stack cô lập, model/service sẵn có, backup/restore | Kubernetes, auto-scaling phân tán, stack observability mới |

### 1.3. Acceptance chung

Mỗi luồng phải có kết quả có kiểu, provenance và status: `answered`, `partial`, `insufficient`, `clarify`, `unsupported`, `provider_unavailable`, `execution_error`. Không biểu diễn thiếu fact bằng 0, không tự đổi literal/đơn vị, không tự suy quan hệ JOIN. Những câu ngoài khả năng phải giải thích bằng tiếng Việt, không trả raw technical errors.

---

## 2. Khóa thiết kế trước coding: Design Approval Gate

> **Đây là một gate, không phải giai đoạn triển khai thứ tư.** Chỉ làm hoạt động nghiên cứu/kiểm kê đọc khi được cho phép. Không cloud calls trả phí mặc định.

### 2.1. Các lựa chọn phải khóa

- [ ] Scope của từng nhóm SQL/RAG/Hybrid và danh sách out-of-scope.
- [ ] Server authority: principal, workspace, catalog, canonical values, approved joins, source revision, rule verdict.
- [ ] Typed query contract, error/status enum, Answer Envelope và conversation trust.
- [ ] Dataset physical storage/revision strategy, permissions và DB roles.
- [ ] Google Sign-In flow, OAuth client và session/CSRF strategy.
- [ ] Ingestion policy cho cloud vs local và data classification; tuyệt đối không tự upload dữ liệu công ty.
- [ ] Đường dùng Gemini API được smoke test với **model+SDK+schema** thực, cùng kế hoạch fallback rõ ràng.
- [ ] Knowledge protocol/auth/IP restrictions đã xác minh bằng tài liệu hoặc approved smoke test.
- [ ] LlamaParse SDK/tier/version/policy/credits rõ ràng.
- [ ] Langfuse server version và SDK compatibility.
- [ ] BGE model identity/path, CUDA/PyTorch/VRAM và model loading topology.
- [ ] Embedding model riêng được chọn bằng test; reranker **không** dùng làm embedding.
- [ ] Corpus/datasets/oracle và held-out hash khóa trước tuning.
- [ ] Live cloud budget, max calls/credits, data privacy, retries/timeout.
- [ ] Ngưỡng latency/cost và denominator của accuracy/false refusal được phê duyệt.

### 2.2. Kiểm kê máy/dịch vụ (read-only; có quyền mới thực hiện)

Báo cáo ngắn dạng bảng: `item | current state | measured/verified evidence | decision | blocker`.

1. Host OS/Docker/Compose version, CPU/RAM/disk/GPU/VRAM, phiên bản NVIDIA driver/CUDA runtime; không sửa driver và không purge images.
2. Các port đang dùng, Compose project/service hiện có; chọn ports ChatSAR không đụng các ứng dụng khác; tuyệt đối không động vào volumes cũ.
3. Model cache BGE thực sự tồn tại: người dùng nói `AAI/bge-reranker-v2-m3`; model card chính thức dùng `BAAI/bge-reranker-v2-m3`. **Xác minh path, config, weights và hash, không tự đổi nhãn/đường dẫn.**
4. Kiểm tra Langfuse version/image/health chỉ đọc; không restart/update; ChatSAR project/API keys mới.
5. Knowledge base URL/model name/auth/protocol/allowlist; chỉ probe từ container khi được phép; các lỗi HTTP 403 được phân loại quyền/network, không xử lý như lỗi prompt.
6. Gemini model availability/rate limits, SDK/Python, response schema compatibility; mặc định không gọi đến khi có live-test budget.
7. LlamaParse quotas, permission, tài liệu được phép gửi; không tải tài liệu nội bộ lên cloud khi chưa duyệt.
8. Google OAuth origins/callback/consent; chọn client riêng của ChatSAR, không đổi cài đặt có thể làm ShopQuery logout.

### 2.3. Biên bản phê duyệt tối thiểu

Ghi trong `docs/DECISIONS.md` hoặc ADR gọn: quyết định, 2 lựa chọn còn lại, bằng chứng/cost/risk, ai duyệt, ngày duyệt, hệ quả kiểm thử. Không tạo một bộ tài liệu khổng lồ cho mỗi câu trả lời nghiên cứu.

**Gate PASS khi:** mọi điểm bảo mật/ngân sách/ownership có quyết định; contract API và benchmark baseline đủ để không đổi dây chuyền giữa các milestone; blocker bên ngoài được nêu rõ, không giả PASS.

---

## 3. Kiến trúc chức năng duy nhất

### 3.1. Topology triển khai

- `web`: React + TypeScript + Vite production build, Nginx proxy `/api`, không chứa secrets.
- `api`: FastAPI/Pydantic, controller, orchestration, catalog, SQL/RAG/Hybrid, providers, user-safe rendering.
- `db`: PostgreSQL + pgvector, persistent volume độc lập, migrations; đọc dữ liệu bằng role riêng ít quyền.
- `worker` **chỉ nếu cần**: ingestion/indexing dài, chạy bằng DB-backed jobs để không mất trạng thái; không bắt buộc Redis.
- `storage`: original uploads, artifacts/manifests/checksums; local volume riêng; BGE/embedding model cache mount chỉ đọc.
- **External/shared:** Gemini và LlamaParse là cloud; Knowledge nội bộ; Langfuse server dùng chung qua project riêng; Google identity dịch vụ ngoài.

Một codebase backend; không triển khai module SQL/RAG/Hybrid thành ba APIs/containers độc lập. Không đưa Langfuse/Knowledge vào Compose ChatSAR nếu chúng đã có dịch vụ riêng.

### 3.2. Luồng yêu cầu

`Google session → server-owned request → verified conversation context → task proposal → catalog/value/document grounding → SQL/RAG/Hybrid execution → evidence/answerability → answer envelope → Vietnamese rendering → durable history + optional Langfuse trace`.

Task routing là **gợi ý chọn luồng**, không phải semantic oracle. Có thể có SQL-only, RAG-only, Hybrid và Clarify. Không tạo classifier thứ hai cho cùng trách nhiệm nếu chưa có benchmark biện minh.

### 3.3. Quyền sở hữu của từng field

| Thông tin | Nguồn thẩm quyền | LLM có được quyết định? |
|---|---|---|
| `user_id`, `workspace_id`, quyền đọc | Server/auth | Không |
| Catalog tables/columns/types/relations/revisions | DB catalog đã xác nhận | Không |
| Raw question, user intent | User | LLM chỉ đề xuất diễn giải |
| Canonical data values và mapping | Dữ liệu/mapping có nguồn | Không tự sinh |
| Query semantic plan | Model proposal + server binding | Chỉ đề xuất |
| SQL execution và numeric facts | Authorized DB + typed executor | Không |
| Policy clauses | Tài liệu đúng phiên bản | LLM chỉ trích xuất ứng viên |
| Policy verdict | Deterministic evaluator khi đủ căn cứ | Không |
| Claim support/answerability | Runtime guards + benchmark gold | Không tự gắn verified |
| Rendered prose | Answer composer | Có, nhưng không được đổi facts |

---

## 4. Repository, conventions và dependency rules

### 4.1. Cấu trúc đích — chỉ tạo thư mục khi dùng

```text
ChatSAR/
├── AGENTS.md
├── README.md
├── Impliment_plan.md
├── .env.example
├── .gitignore
├── compose.yaml
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── auth/
│   │   ├── workspace/
│   │   ├── datasets/
│   │   ├── catalog/
│   │   ├── semantics/
│   │   ├── query/
│   │   ├── documents/
│   │   ├── retrieval/
│   │   ├── hybrid/
│   │   ├── conversation/
│   │   ├── providers/
│   │   └── observability/
│   ├── migrations/
│   └── tests/
├── frontend/
│   └── src/
├── evaluations/
│   ├── datasets/
│   ├── oracles/
│   └── harness/
├── infra/
└── docs/
    ├── ARCHITECTURE.md
    ├── CONTRACTS.md
    ├── CAPABILITIES.md
    ├── TEST_PLAN.md
    └── OPERATIONS.md
```

Không tạo tất cả module từ đầu. `providers` chỉ có adapter thật được dùng. `AGENTS.md` ngắn và tham chiếu file này; không nhân bản 1.000 dòng kế hoạch vào `AGENTS.md`.

### 4.2. Quy chuẩn mã nguồn

- Python type hints và Pydantic strict ở biên, `extra=forbid` khi hợp lý; enum và Decimal/datetime rõ ràng; tên file phản ánh trách nhiệm.
- Backend code không chứa prompt literal rải rác ở 20 file; mỗi tác vụ có một prompt/structured contract có version theo Git commit, không cần hệ thống prompt registry riêng.
- Frontend TypeScript strict, props/API DTO có kiểu, component UI không thực thi business rules hay gọi API key.
- Dùng SQLAlchemy Core để xây SQL; không tạo trình compiler SQL tổng quát hay đưa raw SQL từ LLM trực tiếp vào DB.
- Sửa mã tại nơi chịu trách nhiệm; không tạo `*_old`, `*_backup`, `*_new2` trong production source.
- Comments giải thích các bất biến khó, không chú thích từng dòng hiển nhiên.
- Logging JSON/structured với request ID, không in secrets, PII hoặc raw documents mặc định.
- Dependency pin/lock (Python và Node), Python/Node/image versions khóa sau khi xác minh tương thích; không dùng floating `latest` ở release.
- Không commit caches, model weights, DB dumps, uploaded raw data, traces chứa PII, build outputs, credentials, `.env` secrets, temporary benchmark artifacts.

### 4.3. Lệnh/entrypoints chuẩn hóa (tên cụ thể do Codex chốt trong PR đầu)

Codex phải tạo và tài liệu hóa **một lệnh cho mỗi hành vi**: build, lint, typecheck, backend tests, PostgreSQL integration tests, frontend tests, browser E2E, fixture import, evaluation, migrate, compose up/down, backup/restore. Không tạo 3 script cùng chức năng. Khả năng chạy test DB độc lập không được yêu cầu xóa volumes đang dùng.

---

## 5. Database, metadata, revisions và isolation

### 5.1. Data ownership

- App tables: `users`, `sessions`, `workspaces`, `datasets`, `dataset_revisions`, `catalog_tables`, `catalog_columns`, `approved_relationships`, `ingestion_jobs`, `documents`, `document_revisions`, `document_chunks`, `conversations`, `messages`, `result_records`, `result_evidence`, `provider_usage` (triển khai khi cần).
- Dữ liệu CSV/XLSX publish thành **bảng PostgreSQL có kiểu** theo dataset/revision; internal identifier do server sinh, không ghép raw filename/tên cột từ user trực tiếp thành SQL.
- Mỗi document/dataset là một source revision bất biến sau publish. Sửa dữ liệu → tạo revision mới; câu trả lời cũ giữ nguồn revision hoặc báo đã cũ, không lặng lẽ thay số liệu.
- PostgreSQL role migration/admin, app metadata writer và query reader ít quyền phải được phân biệt. Query reader chỉ có quyền SELECT phù hợp; không được là owner/superuser/BYPASSRLS.
- Không cho model hay HTTP request tùy ý chọn schema/table. Query compiler chỉ dùng `Table/Column` objects từ allowlisted catalog đã kiểm quyền theo workspace; guard quyền ở mọi endpoint/result/citation.
- RLS cho bảng app dùng chung là defense-in-depth nếu triển khai; không tuyên bố RLS tự động áp dụng mọi physical dataset table. Cơ chế isolation chính của MVP là server-owned binding + query reader + negative tests thực.

### 5.2. Metadata tối thiểu

`table_id`, `table_description`, `column_id/name/type/nullable/description`, `primary_key`, `unique_keys`, `foreign_key`, `relationship_cardinality`, `join_direction`, `grain`, `unit`, `timezone`, `source_revision`, `approved_synonyms`, `value_mapping_provenance`, `completeness_policy`.

`grain` mô tả một dòng tương ứng gì; `completeness_policy` không tự suy từ việc dữ liệu có mặt. Đặc biệt, `id` trong tên cột không đồng nghĩa NOT NULL hoặc PK.

### 5.3. CSV/XLSX ingestion

1. **Receive:** validate file extension, content signature/MIME, size, zip/worksheet limits, checksum, owner workspace; lưu original vào storage riêng.
2. **Parse:** CSV xử lý UTF-8 BOM/delimiter/quote, XLSX chọn sheet; không đánh giá/executing Excel formulas; thông báo cached formula values hoặc thiếu cache.
3. **Profile:** infer candidate types, nullable, uniqueness, duplicates, leading-zero TEXT IDs, decimal/date locale, sample values, possible relationships. Đây là **gợi ý**, không auto-trust.
4. **Review UI:** user xác nhận types, keys, aliases, grain/units và relationship; hiển thị cảnh báo mất precision/date ambiguities.
5. **Normalize:** chuyển sang PostgreSQL với kiểu được xác nhận; lỗi row-level có thông báo, không tự bỏ hàng/ép float cho tiền; lưu row/source provenance.
6. **Publish atomically:** tạo physical table/revision và catalog; kiểm row count/checksums; chỉ sau đó đặt `ready`.
7. **Recover:** job có trạng thái durable, idempotent theo file checksum + config/revision; restart không làm mất upload đã publish hoặc charge/reparse vô hạn.

Giới hạn thử đầu: ~20 MiB/file, 50.000 rows/sheet; enforce server-side và tune bằng test, không quảng cáo hỗ trợ mọi file.

### 5.4. Data invariants bắt buộc

- `COUNT(*)` khác `COUNT(col)` khác `COUNT(DISTINCT col)`.
- `NUMERIC/Decimal` cho metric tiền tệ và phép tính chính xác; không chuyển sang binary float rồi định dạng lại.
- `NULL`, zero và không có fact là ba trạng thái khác nhau; không đánh giá entity không có fact là fail/zero nếu thiếu completeness evidence.
- TEXT IDs giữ leading zeros; ngày và timezone được gắn context rõ; khoảng thời gian dạng `[start, end)` nơi phù hợp.
- Cardinality/grain của JOIN được xác thực; không được nhân dòng fact gây sai aggregate.
- DISTINCT không được dùng làm mẹo vá fanout của JOIN sai.
- Source revision và query provenance phải đủ để kiểm tra hoặc tái thực thi có kiểm soát.

### 5.5. SQL physical layout cần prototype trước khi khóa

Ưu tiên `data` schema riêng chứa physical tables sinh bằng identifiers không đoán được, gắn catalog `workspace_id + revision_id`; không schema-per-user phức tạp khi chưa có nhu cầu. Trước khi duyệt layout, viết proof-of-concept trên PostgreSQL cô lập chứng minh: create revision; query đúng bảng; query reader không DDL; owner A không đọc B qua API/compiled SQL; rollback ingestion không lộ bảng ở trạng thái half-published. Nếu model chọn bảng lạ, trả lỗi có kiểm soát.

---

## 6. Contract chung và API behavior

### 6.1. Core typed semantics

`AuthorizedRequest`: server-derived `principal`, `workspace_id`, `dataset_revision_id` và `document_revision_ids`, `question`, `reference_datetime`, `timezone`, `capabilities`, `conversation_reference` nếu hợp lệ.

`TaskProposal`: `SQL | RAG | HYBRID | CLARIFY | UNSUPPORTED`, `raw_user_spans`, `candidate_entities`, `metrics`, `predicates`, `needs_clarification`, `unresolved`; output LLM luôn **untrusted**.

`GroundedQuery`: `population`, `metric`, `aggregation`, `distinct_semantics`, `nullable_policy`, `source_tables`, `typed_literals` + provenance, `filters` (AND/OR tree), `time_interval`, `approved_join_edges`, `group_by`, `output_selection`, `order_by`, `limit`, `grain`.

`EvidencePlan`: `required_sql_sources`, `required_document_sources`, `source_revisions`, `coverage_obligations`, `unresolved_clauses`.

`ExecutionResult`: `typed_columns`, `rows`, `metric/unit`, `source_revision`, `row_count`, `query_provenance`, `warnings`.

`PolicyEvaluation`: `policy_source`, `effective_interval`, `metric/threshold/operator/unit`, `population`, `applicability`, `per_entity_verdict`, `missing_data_policy`.

`AnswerEnvelope`: `status`, `facts`, `display_rows`, `citations`, `limitations`, `display_text`, `request_id`.

`ConversationReference`: `verified_result | reference_only | ineligible` với `plan_ref`, `source_revision`, `result_ref`, `evidence_refs`.

Không buộc mỗi đối tượng thành microservice hoặc generic framework. Chỉ tạo model thực sự phục vụ boundary/validation.

### 6.2. API tối thiểu, không thêm endpoint không sử dụng

| Method | Endpoint | Security/behavior bắt buộc |
|---|---|---|
| POST | `/api/auth/google` | Verify token + CSRF theo flow; tạo session server-side |
| POST | `/api/auth/logout` | Revoke session; cookie clear |
| GET | `/api/me` | Server-derived user |
| GET,POST | `/api/workspaces` | Owner scoped; create/list |
| POST | `/api/workspaces/{workspace_id}/datasets` | Auth upload; create job |
| GET | `/api/datasets/{dataset_id}/preview` | Owner + revision check, paginate |
| POST | `/api/datasets/{dataset_id}/confirm` | Validate types/keys/relationships; publish |
| POST | `/api/workspaces/{workspace_id}/documents` | Upload protected file; create parse job |
| GET | `/api/jobs/{job_id}` | Real durable progress, owner checked |
| GET | `/api/documents/{document_id}/source` | Citation/preview/download authorization |
| GET,POST | `/api/conversations` | Owner scoped |
| GET | `/api/conversations/{conversation_id}` | Owner scoped messages + result refs |
| POST | `/api/conversations/{conversation_id}/messages` | Idempotency, request scope, normalized response |
| GET | `/api/results/{result_id}` | Owner + source version + evidence permissions |
| GET | `/live`, `/ready`, `/health` | Không gọi cloud trả phí; không lộ secrets |

API response phải có `request_id`, public error code ổn định và thông báo người dùng phù hợp. Status HTTP chỉ phản ánh transport; `answer_status` mô tả answerability, không lẫn 200 với verified.

### 6.3. Idempotency và consistency

- Chat send dùng client request key để tránh gửi/gọi cloud lặp khi frontend retry hoặc timeout.
- Upload/parse job lưu checkpoints và state; chỉ một revision được publish cho cùng công việc idempotent.
- Mỗi answer gắn dataset/doc revision đã được chốt tại request time; nếu revision thay trong lúc chạy, giữ snapshot hợp lệ hoặc dừng bằng trạng thái nguồn đã thay đổi.
- Cancel UI không được hiểu thành DB/LLM task đã bị hủy nếu chưa có cancellation semantics; hiển thị trạng thái đúng.

---

## 7. Text-to-SQL implementation specification

### 7.1. Pipeline duy nhất

`Question → verified follow-up context → schema/value candidates → LLM structured proposal → server grounding/binding → typed query plan → SQLAlchemy Core compiler → validation → read-only PostgreSQL execution → typed result → natural answer`.

Trước tiên đo single-call structured plan; chỉ thử staged reasoning khi single-call không đạt target và cải thiện được chứng minh bằng test. Không dùng ba agent để sinh/review/fix SQL mặc định.

### 7.2. Schema grounding

- Lấy thông tin bảng/cột/relation được cấp quyền từ catalog; không đưa toàn bộ schema nếu không cần.
- Với ≤10–20 bảng demo, ưu tiên deterministic filtering bằng schema descriptions/metadata và join connectivity; schema embedding retrieval chỉ thêm khi chứng minh tăng quality.
- Khi cùng tên cột trong nhiều bảng, binding phải dùng internal catalog IDs, không chỉ string names.
- Model có thể đề xuất bảng/cột; server kiểm tra chúng thuộc catalog và workspace hiện hành.
- Nếu có nhiều đường JOIN hợp lý hoặc không có approved relationships, `clarify`/`unsupported`, không suy JOIN từ tên `_id`.

### 7.3. Value grounding

- Với mỗi literal: lưu user phrase gốc, type kỳ vọng, model candidate, canonical value và mapping/evidence source.
- Exact match → mapping đã được duyệt → ứng viên tìm gần đúng; fuzzy/normalization không tự biến thành canonical nếu có nguy cơ đổi nghĩa.
- Phép so sánh phải theo kiểu cột (date, numeric, text, bool); `"quận 3"` không tự thành `"3"`; `"0007"` không thành `7` khi cột là TEXT.
- Với private values, hạn chế examples/cardinality trong prompt; query tìm ứng viên được scope theo quyền, không log raw values vào Langfuse mặc định.
- Ambiguous year, units, enum values, conflicting aliases phải trả `clarify` khi ảnh hưởng kết quả.

### 7.4. Typed query plan grammar MVP

Hỗ trợ số ít phép toán đã nêu: `select_columns`, `COUNT_ROWS`, `COUNT_NON_NULL`, `COUNT_DISTINCT`, `SUM`, `AVG`, `MIN`, `MAX`, `EQ`, `NE`, `GT`, `GTE`, `LT`, `LTE`, `IN` có size cap, `IS_NULL`, `IS_NOT_NULL`, `AND`, `OR`, `[start,end)` cho datetime, `GROUP_BY`, `ORDER_BY`, `LIMIT`, `INNER JOIN`/`LEFT JOIN` chỉ khi có approved edge.

- Tách `evaluation_population`, `input_predicates`, `policy_applicability`, `output_selection` để Hybrid không lẫn phạm vi.
- Khi aggregate của bảng fact cần join dimension N:1, kiểm cardinality và metrics ở đúng grain.
- Nhiều bảng fact 1:N:N gây nhân dòng thì **không** cho chạy phép SUM trực tiếp. Chỉ mở hỗ trợ pre-aggregation nếu có oracle và ngữ nghĩa rõ; không dùng `DISTINCT` che fanout.
- Không đưa SQL expression strings từ LLM (`HAVING foo()`, `CAST arbitrary`, raw ORDER BY) vào compiler.
- Giới hạn alias, result columns, `LIMIT` trong backend; input limits không chỉ là prompt instructions.

### 7.5. Query validation checklist theo thứ tự

| Gate | Kiểm tra | Failure behavior |
|---|---|---|
| G1 | Pydantic strict structure, enum/operator, không dư fields nguy hiểm | Reject proposal; trả clarify/error có kiểm soát |
| G2 | Principal/workspace/catalog revision | Không truy cập source ngoài quyền |
| G3 | Column/type/metric/units/literal binding | Clarify nếu không đủ căn cứ |
| G4 | All known user qualifiers represented, AND/OR/time/order/limit | Block/clarify khi phát hiện mất nghĩa; semantic unseen eval song song |
| G5 | Join approved, key cardinality, grain/fanout | Block ambiguous/unsafe aggregation |
| G6 | SQLAlchemy compilation, no raw SQL/DDL/DML, bound params | Reject unsupported plan |
| G7 | DB readonly role, timeout, result cap; EXPLAIN (no ANALYZE) tùy cần | Cancel/limit query có lỗi thân thiện |
| G8 | Typed rows, source revision, sanity checks, result envelope | Trả dữ liệu thực, không tự thay bởi model |

**Giới hạn kiểm tra:** các bước trên phát hiện nhiều lỗi kỹ thuật và một phần lỗi ngữ nghĩa, nhưng không chứng minh model hiểu đúng 100% câu gốc. Bắt buộc có independent oracle cross-domain và positive/negative cases.

### 7.6. PostgreSQL execution

- Role chỉ SELECT trong analytical objects được cấp, không migration privilege, không superuser.
- Connection/session có transaction read-only, parameter binding, `statement_timeout`, resource limits và query/result caps.
- `EXPLAIN (FORMAT JSON)` không có `ANALYZE` chỉ khi có lý do preflight; cost estimates không phải chứng nhận an toàn hay semantic correctness.
- Pagination cho bảng kết quả; không serialise Decimal thành float; NULL thành null, DATE/TIMESTAMP có timezone rõ, text IDs giữ nguyên.
- Không dùng SQL string interpolation cho identifiers từ user hoặc query content. Compiler nhận whitelisted objects từ catalog.
- Khi query fail: không trả fabricated rows; lỗi ảo/sai quyền/timeout được phân loại riêng; tối đa một lần retry/sửa kỹ thuật khi có bằng chứng và budget.

### 7.7. SQL benchmark cases bắt buộc

- Simple filter/sort/limit: AND/OR, dấu, casing, literals chính xác.
- COUNT rows vs column vs distinct, group by đúng grain.
- SUM/AVG Decimal + NULL và precision; empty set/NULL aggregate.
- Dates: timezone, timestamp boundaries `[start,end)`, qua tháng/năm.
- JOIN 1:N, N:1, 1:1, không match, orphan, nullable FK; fanout traps, dual-path joins.
- Raw phrase “quận 3” khác “3”, ID dạng text “0012”, mốc thời gian và đơn vị không được tự sửa.
- Ambiguous column/metric/unit/year; hỏi làm rõ khi ảnh hưởng kết quả.
- Negative: unknown table, forbidden schema, unauthorized workspace, DDL/DML, injected SQL, query quá lớn.
- Metamorphic: paraphrase giữ kết quả; thay filter đổi đúng subset; reorder rows không đổi SUM; thêm irrelevant records không đổi result.

### 7.8. Completion criteria SQL

Người dùng có thể tải hai schema khác nhau, xác nhận metadata, hỏi SQL một bảng và (sau giai đoạn 2) multi-table, xem kết quả/nguồn qua UI. Oracle PostgreSQL độc lập khớp; không có critical silent wrong qualifiers, unauthorized access, fanout sai hoặc COUNT/NULL/Decimal sai. Model-live được ghi riêng, không lấy mock làm chứng cứ.

---

## 8. RAG ingestion và indexing

### 8.1. Normalized document contract

Mỗi document revision chứa original checksum, content type, parser+version+options, source pages/sections, raw extracted content, normalized text, headings, tables, offsets/anchors, language, owner, parse status và indexing status.

Mỗi chunk chứa: chunk ID, document ID, revision ID, workspace ID, text, heading path, page start/end, source offset, chunker config, embedding model ID/revision/dimension và checksum. Citation phải mở được nguồn gốc nguyên bản, không chỉ đoạn text do model viết lại.

### 8.2. Parser selection

- TXT/Markdown: local decode và parse; không gọi LlamaParse.
- DOCX: local parser giữ đoạn/heading/bảng; không làm rơi nội dung quan trọng trong phạm vi demo.
- PDF có text: PyMuPDF local baseline, kiểm reading order, multi-column; Docling là ứng viên local khi layout khó.
- PDF khó: LlamaParse chỉ khi cloud/data policy cho phép; benchmark tier Cost Effective và Agentic nếu cần.
- OCR scan/biểu đồ chưa có benchmark: thông báo unsupported/partial, không hứa hỗ trợ.

### 8.3. Cleaning không được đổi nghĩa

- Unicode, whitespace, line wraps có kiểm soát; giữ phủ định, con số, dấu, toán tử, đơn vị, ngày và mã.
- Header/footer lặp lại chỉ xóa khi chứng minh không phải nội dung; luôn giữ raw source.
- Bảng phải giữ column headers/captions/row alignment; chunk của row không được mất nghĩa cột.
- Parser mất trang hoặc cột dữ liệu quan trọng: cảnh báo/needs_review, không tự đánh ready.
- Parse cache theo checksum + parser ID/version/options, kiểm quyền và dedupe chi phí cloud.

### 8.4. Chunking

- Chia theo heading/section/paragraph/table trước, token limit sau.
- Thử 350–600 tokens/chunk, overlap 50–80 nếu cần; không chặt ngang quy định, bảng hoặc điều kiện hiệu lực.
- Lưu mapping chunk → source revision/page/offset; kiểm khả năng mở lại raw excerpt đúng từ UI.

### 8.5. Embedding và pgvector

- BGE reranker **không** làm embedding. Benchmark BGE-M3 hoặc model multilingual nhẹ hơn trong giới hạn VRAM/latency.
- Lưu embedding model ID/revision/dimension/normalization; đổi embedding model → reindex có kiểm soát; không trộn vectors không tương thích.
- Corpus nhỏ bắt đầu exact search; đo hiệu quả HNSW/ANN trước khi thêm index approximate.
- Workspace/revision security filter nằm trong truy vấn có kiểm soát; không lấy cross-owner candidates rồi mới ẩn ở UI.
- Index/reindex idempotent và có recovery sau restart.

### 8.6. Job states

`uploaded → validating → parsing → normalizing → chunking → embedding → indexing → ready`, ngoài ra `needs_review`, `failed`, `cancelled` khi semantics rõ. Mọi trạng thái nằm trong DB; FE polling; không mô phỏng progress bằng timer. Worker chết phải resume tại checkpoint hợp lệ hoặc fail/retryable có kiểm soát. Không lặp cloud charge vượt ngân sách.

---

## 9. Retrieval, BGE reranker và RAG evidence

### 9.1. Benchmark retrieval ba cấu hình

A. Dense vector only.  
B. Dense + lexical/keyword + RRF/dedup.  
C. Dense + lexical + BGE local reranking.

Không mặc định C tốt nhất; đo Recall@k, MRR/nDCG khi có gold ranking, claim support, answer completeness, p50/p95, peak GPU memory và cost. Corpus phải chứa văn bản tiếng Việt, mã định danh, bản dịch/biến thể, điều khoản ngoại lệ.

### 9.2. Retrieval runtime

1. Dùng câu hỏi và verified context; không dùng câu trả lời văn xuôi chưa xác minh làm fact.
2. Filter workspace/doc revisions/permissions trước candidate retrieval.
3. Dense top-k thử 20, lexical top-k thử 20; lưu ý PostgreSQL full-text mặc định chưa chắc tách từ tiếng Việt tốt.
4. Kết hợp thứ hạng bằng RRF/dedup; chọn 10–20 candidates đi rerank.
5. `BAAI/bge-reranker-v2-m3` chấm query-passage, batch thử 4/8, max length 512/1024, FP32 baseline và FP16 benchmark.
6. Chọn 4–6 evidence chunks hoặc mở rộng adjacent section/page khi chính sách hay bảng bị cắt.
7. LLM synthesis dùng only supplied evidence, citation IDs từ backend; thiếu điều kiện thì partial/insufficient.

Reranker score là relevance, không phải xác suất claim đúng và không được dùng như policy oracle.

### 9.3. Triển khai BGE local

- Xác minh actual local path, weights, model config và nhận diện model chính thức `BAAI/bge-reranker-v2-m3`; không tự tải weights bất ngờ. User ghi `AAI/...` là thông tin cần xác minh, không tự sửa path.
- Mount read-only, offline loading khi runtime hỗ trợ; pin model/Transformers/Torch/FlagEmbedding.
- Một instance/process; tránh nhiều Uvicorn workers nhân VRAM. Nếu GPU contention cao, lựa chọn 1 inference worker hoặc tách tối thiểu sau benchmark.
- Warm-up có kiểm soát; health endpoints không nạp lại model hoặc gọi cloud.
- GPU failure: báo trạng thái hoặc explicit fallback; không silently chuyển CPU làm demo treo.
- Test batch, tiếng Việt, long chunks, empty candidate set, OOM, restart và cross-owner filtering.

### 9.4. Citation verification

Runtime phải kiểm evidence ID tồn tại, đúng owner/workspace/revision, raw excerpt còn truy xuất được và numeric/entity facts không bị presentation sửa. Benchmark và human-reviewed gold phải đánh giá claim thực sự được hỗ trợ và coverage đầy đủ; citation membership ≠ claim support.

Negative: PDF nhiều cột, bảng thiếu header, contradictory docs, wrong revision, tài liệu prompt injection, câu không có đáp án, file lỗi, expired permissions, reranker/embedding offline.

---

## 10. Hybrid SQL + RAG

### 10.1. Mode A — số liệu + tài liệu giải thích

- Planner tách phần cần SQL facts và phần cần document evidence trong cùng scope/time.
- SQL trả typed metrics; RAG trả đoạn tài liệu có quan hệ entity/time có căn cứ.
- Không biến tương quan/nhận định từ tài liệu thành nguyên nhân đã chứng minh.
- Nếu thiếu một nhánh, trả partial cùng phần đã xác minh; không tự bù dữ liệu còn thiếu.

### 10.2. Mode B — policy threshold đơn giản

Grammar: metric ID, operator (>, >=, <, <=, =), Decimal threshold, unit, evaluation population, applicability, validity interval, source clause, missing-data policy. Nhiều ngoại lệ lồng nhau nằm ngoài MVP nếu chưa có oracle.

Trình tự bất biến:

1. Retrieve đúng điều khoản, nguồn, revision, ngày hiệu lực và đầy đủ ngữ cảnh.
2. Chuyển thành policy candidate; xác minh metric, unit, applicability, ambiguity (yêu cầu làm rõ nếu cần).
3. Liệt kê **entity universe** đủ điều kiện được đánh giá; không bắt đầu từ fact table rồi loại entity không có fact.
4. Tính facts mỗi entity bằng authorized SQL và đúng grain, dates, NULL semantics.
5. Đánh giá tất định bằng Decimal → PASS / FAIL / UNKNOWN / NOT_APPLICABLE.
6. **Sau khi đánh giá** mới chọn chỉ không đạt, sort hoặc limit.
7. Trả nguồn chính sách, metric/data revision và số trường hợp unknown; không giấu thiếu dữ liệu.

Oracle ví dụ: threshold 10 triệu, A có 12 triệu → PASS; B có 8 triệu → FAIL; C không có fact, chưa có completeness guarantee → UNKNOWN. Không tự gán C = 0.

### 10.3. Hybrid negative tests

- Evaluation population khác input predicate/output selection; policy hiệu lực sai kỳ; unit khác.
- Missing fact/NULL/zero, completeness, policy applicability NOT_APPLICABLE.
- Policy-only có chữ “KPI” nhưng không cần SQL; SQL-only chứa từ “quy định” trong tên nhưng không cần document.
- Có nhiều policy thresholds mâu thuẫn và chưa xác nhận nguồn; tuyệt đối không chọn một policy ngẫu nhiên.

---

## 11. Trả lời tự nhiên và hội thoại

### 11.1. Unified Answer Envelope

`status`, `facts` (numeric/display rows, metric/unit/scope/revision), `citations` (typed source refs), `limitations`, `display_text`, `request_id`. LLM không được đổi facts hoặc tự gắn status verified.

### 11.2. Rendering

- SQL count/scalar/table đơn giản: template deterministic, tránh model call và tránh đổi số.
- RAG/Hybrid: một synthesis call nếu cần; answer checks kiểm numeric/citation/entity/status, fallback template hoặc partial khi claim không đủ căn cứ.
- UI tiếng Việt, rõ ràng, không stack traces/JSON/internal aliases; nguồn/cách tính có panel mở rộng riêng.
- Có phân biệt answered/partial/insufficient/clarify/unsupported/provider_unavailable/execution_error với copy thân thiện.

### 11.3. Conversation trust

- `verified_result`, `reference_only`, `ineligible` theo bằng chứng. HTTP200/error=null không được nâng trust.
- Follow-up kế thừa typed verified plan/revisions, không dùng assistant prose làm ground truth.
- Stale revision → báo thay đổi hoặc re-run có chủ đích. Partial/error/unsupported turn không trở thành premise verified.
- Chuyển workspace → không mang nguồn cũ không được cấp quyền sang context mới.

---

## 12. Sáu công nghệ hiện có: khai báo, tương thích, kiểm thử

### 12.1. Quy tắc adapter thống nhất

Mọi provider adapter cần có: một đường gọi chính thức, enable/disable, timeout, retry có giới hạn, usage/cost status, error taxonomy, request IDs, redaction, validation và tests mock/offline. Chỉ một LLM làm primary mỗi lượt; provider thứ hai dùng đối chứng hoặc fallback được bật rõ. Cloud OFF và budget 0 mặc định.

### 12.2. Gemini 3.5 Flash-Lite

- SDK ứng viên `google-genai`, model ID `gemini-3.5-flash-lite`; model access/rate limit theo chính project/API key.
- Xem API tài liệu Structured Output hiện thời. **Chọn một** giao thức được thử thật cho schema Query Plan: Interactions API với `response_format` hoặc đường khác chính thức nếu compatibility đòi hỏi; không trộn nhiều SDK paths trong runtime.
- Smoke test parser chính JSON Schema/Pydantic, nested fields/enum/nullable, error shapes, 400/401/403/429/503, usage và latency. Nếu native schema không tương thích, phân tích giới hạn, sửa schema có kiểm chứng hoặc điều chỉnh contract; không tự mặc định JSON prompt là an toàn về ngữ nghĩa.
- Structured output chỉ bảo đảm hình thức trong phạm vi provider support; semantic test bằng PostgreSQL oracle là riêng.
- Bật model-live chỉ khi người dùng duyệt max requests/tokens/budget và loại dữ liệu gửi đi. No silent model fallback.

### 12.3. Knowledge do công ty host

- Dùng configured `base_url`, model `knowledge`, credential qua environment/secret; endpoint có OpenAI-compatible Chat Completions hay không phải kiểm tra thật.
- Kiểm từ container: DNS/TLS, IP allowlist, HTTP auth, request/response field shapes, max tokens, JSON capability, usage, timeout, concurrency; không đoán mọi option OpenAI đều hoạt động.
- HTTP 403 → phân tích permission/IP, không prompt tuning. So sánh với Gemini trên cùng benchmark và đủ điều kiện privacy.
- Không gửi secrets/raw company model responses vào public logs.

### 12.4. LlamaParse

- SDK hiện hành theo docs `llama-cloud`, `LlamaCloud`/`AsyncLlamaCloud`, biến `LLAMA_CLOUD_API_KEY`.
- Tier `fast` chỉ text/spatial text, không có Markdown; dùng `cost_effective` nếu cần Markdown cấu trúc, Agentic chỉ khi bảng/layout khó và được duyệt chi phí.
- Parser output chuẩn hóa về document contract của ChatSAR; cache theo checksum/parser version/options; persist job status và credit accounting.
- SDK `parsing.parse` có thể block đến hoàn thành; không block HTTP handler dài; dùng job executor và persisted state.
- Lock parser/tier/version sau verified smoke, không phụ thuộc `latest` trong release; tuyệt đối không auto upload file private.

### 12.5. Local BGE reranker

- Model chính thức là `BAAI/bge-reranker-v2-m3`, nhưng local path phải inventory; user ghi `AAI/...` có thể là đường dẫn/tên nội bộ khác, không tự thay thế.
- Chọn FlagEmbedding **hoặc** SentenceTransformers CrossEncoder sau một phép benchmark; tránh hai inference implementations cùng tồn tại.
- Test local/offline model loading, CUDA, batch, FP32/FP16, VRAM, rank changes, OOM/failure; một loaded copy/process, model cache read-only.
- Không nhầm với `BAAI/bge-m3` embedding model; embedding model vẫn là lựa chọn cần test.

### 12.6. Langfuse hiện hữu

- **Dùng lại server, không deploy/cập nhật/restart server cũ.** Kiểm server version read-only và network accessibility; tạo project/API keys ChatSAR riêng.
- Compatibility self-hosted (tài liệu kiểm 29/10/2026): Python SDK v4 phù hợp self-hosted v3.63+ hoặc v4 hỗ trợ; Python SDK v5 cần server v4.59+. Chọn theo server thực và pin.
- Trace root theo request; children cho operations thực sự; ghi provider/model/latency/tokens/credits/status mà không lưu raw user data hoặc secrets mặc định.
- Langfuse failure không chặn chức năng chính. Không dùng Langfuse thay budget enforcement/database chat.

### 12.7. Google Sign-In

- Dùng Google Identity Services, OAuth Web Client riêng ChatSAR và origin/redirect hợp lệ; chỉ scopes cần login.
- Backend verify ID token signature/iss/aud/exp; CSRF double-submit token cho GIS POST flow (hoặc biện pháp tương đương phù hợp flow xác nhận), kiểm token replay/nonce nơi áp dụng.
- Internal account key liên kết Google `sub`; email chỉ là profile; unique index theo provider + sub.
- Session local trong DB, secure cookie HttpOnly, Secure trong HTTPS, SameSite phù hợp, session expiry/revoke, anti-CSRF cho state-changing routes.
- Mọi workspace/dataset/chat/document/evidence/result owner-checked; không tin ID từ FE.

### 12.8. Cấu hình ứng dụng dự kiến (key names, không chứa secrets)

| Nhóm | Cấu hình cần tồn tại | Default/policy |
|---|---|---|
| App | `APP_ENV`, `DATABASE_URL`, `SESSION_SECRET` | Startup validation |
| Google | `GOOGLE_CLIENT_ID`, approved origins | Login only |
| Gemini | `GEMINI_ENABLED`, `GEMINI_API_KEY`, `GEMINI_MODEL` | OFF cho đến approved |
| Knowledge | `KNOWLEDGE_ENABLED`, `KNOWLEDGE_BASE_URL`, `KNOWLEDGE_API_KEY`, `KNOWLEDGE_MODEL` | Không assume protocol |
| LlamaParse | `LLAMAPARSE_ENABLED`, `LLAMA_CLOUD_API_KEY`, `LLAMAPARSE_TIER` | OFF cho đến approved |
| Retrieval | `EMBEDDING_MODEL_PATH`, `RERANKER_MODEL_PATH`, `RERANKER_DEVICE` | Local, kiểm model identity |
| Langfuse | `LANGFUSE_ENABLED`, `LANGFUSE_BASE_URL`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | Project ChatSAR mới |
| Cloud policy | `CLOUD_CALLS_ALLOWED`, `CLOUD_MAX_REQUESTS`, `CLOUD_BUDGET_USD` | false / 0 / 0 |

Config được Pydantic Settings kiểm tra điều kiện: secrets chỉ bắt buộc khi provider bật; limit được **enforce ở backend trước mỗi cloud call**, không chỉ ghi `.env` cho đẹp. Theo dõi budget bền vững trong DB, tính retry. Không ghi API keys vào traces/tests/console.

---

## 13. Frontend implementation specification

### 13.1. Tech và layout

React + TypeScript strict + Vite + React Router. UI sáng, màu xanh lam nhẹ; desktop-first responsive; sidebar trái (workspace, new chat, history, datasets, documents, settings); chat ở giữa; drawer evidence có thể mở/đóng. FE không tự kiểm chứng SQL/policy; mọi nghiệp vụ ở server.

### 13.2. Các screen và trạng thái

| Screen | Bắt buộc | Empty/loading/error/permission cases |
|---|---|---|
| Login | Google Sign-In, logout/session | Invalid token, expired session, denied auth |
| Workspaces | Create/list/select, owner filter | Zero workspace, forbidden workspace |
| Dataset Manager | CSV/XLSX upload, choose sheet, data preview, review types/keys/relationships, publish | Unsupported file, size limit, invalid rows, user review pending |
| Chat | Compose/send, source scope chips, answer status, result table, follow-up, history | Clarify, provider unavailable, execution error, partial |
| Document Manager | Upload, parse/index progress, document list/revision, view source | Parser failure, stale revision, missing page |
| Evidence Drawer | SQL source, filters, metric, typed table; document citation page/excerpt | Forbidden citation, missing source |
| Settings | Session, provider status (no keys), basic usage | Provider disabled/unavailable |

### 13.3. FE behavior

- Server is source of truth; use typed DTOs/runtime validation for API responses, no untyped `any` for critical flows.
- Progress reflects persisted job states, not a fake percentage timer. If only stage known, display stage rather than fabricated percentage.
- Show Vietnamese natural answers and expandable sources. UI can show SQL/query plan only in developer/source panel with permission, not in main answer.
- Client-side filters do not replace server authorization, pagination or query limits.
- Disable duplicate send during pending request, preserve idempotency key when retrying; on reconnect restore last stable state.
- User-facing tables preserve Decimal formatting, null/missing distinction, timezone; CSV export protect spreadsheet formula injection.
- No provider API keys in frontend bundle, localStorage or querystring. Auth via secure server session, not tokens hidden in FE files.
- Document citation click checks authorization server-side and opens exact revision/page/span where format permits; otherwise explain source position is approximate instead of inventing it.

### 13.4. FE test matrix

Login success/failure/logout; workspace create/switch; owner A/B isolation; upload good/bad CSV/XLSX; preview/map/publish; chat answered/partial/clarify/unsupported/error; document job progress and recovery; open citation; refresh retains history; stale source; long answer/table; mobile drawer; no uncaught errors; no raw traceback/aliases in normal UI.

---

## 14. Security, Docker, reliability và operations

### 14.1. Threats & boundaries

- Injection: user questions, document prompt injection, malicious CSV/XLSX/PDF/DOCX, broken or forged metadata, direct object reference, SQL parameter injection, CSRF/XSS, SSRF, rate-limit abuse.
- Enforce auth/ownership **before** retrieval/SQL and again when reading result/document citation. External document content is data, never instructions overriding trusted system policy.
- Limit upload bytes, decompression ratio, pages/rows/cells; sanitize original filename and storage paths; never execute macro/formula or external links by default.
- DB query reader read-only; no arbitrary SQL, no unrestricted system catalogs/function calls; resource/timeout/result caps.
- Secrets at runtime only, PII-safe logs/traces, cloud data classification; backups restricted and encrypted if sensitivity requires.
- Zero tolerance for cross-owner leak, unauthorized cloud upload or silent data mutation.

### 14.2. Docker plan

- Compose project name ChatSAR-specific; port allocation only after inventory; never reuse ShopQuery volumes/networks/DB.
- Services: `web`, `api`, `db`; worker optional on evidence; no duplicate Langfuse/Knowledge containers.
- Non-root API/web processes where feasible; minimal pinned images; healthchecks and dependency readiness; no dev hot reload for release.
- Mount BGE cache read-only and persistent uploads separately; PG persistent volume with backup/restore proof.
- Initially one API process if BGE embedded to avoid multiply loading GPU weights. Do not assume Docker GPU passthrough is working without test.
- `/live`: application process; `/ready`: local critical deps+DB+migrations; `/health`: safe aggregated status without calling paid providers.

### 14.3. Persistence, backup, restore, rollback

- Backup PostgreSQL plus file artifacts, checksums/manifests; restore test into **isolated** destination and verify row counts, IDs, access ownership, document citations and source files.
- Docker restart/recreate retains users, sessions per policy, workspaces, datasets, messages, source revisions/chunks and jobs.
- Rollback points at exact image digest/commit and schema compatibility; migration downgrade may be unsafe, so require backup + forward-compatible rollout strategy.
- No broad `docker system prune --volumes`, `docker volume prune`, deleting old image/tag by pattern, force push or touching project other than ChatSAR.
- Release includes commands for start/stop/health, migration, backup/restore, log inspection, rollback; every destructive command must target exact resources.

### 14.4. Observability/error states

Structured logs carry request/session/workspace pseudonymous IDs and error category; Langfuse traces show actual operation spans, model name, token/credit usage, latency. Default no raw PII/files. Provider 400/401/403 diagnosis ≠ transient; bounded retries for 429/5xx/timeouts within budget, with idempotency handling.

---

## 15. Đề xuất thứ tự công việc: dependency DAG

**Không được đảo thứ tự để làm phần dễ trưng bày trước phần quyết định correctness.**

```text
Design Approval / benchmark gold / read-only inventory
                    |
                    v
Repo + Docker isolation + DB + CI + API contract
                    |
                    v
Google auth / workspace / owner isolation
                    |
                    v
CSV/XLSX upload → catalog → preview → publish revision
                    |
                    v
Typed Task → Value Grounding → SQL compiler → PG oracle
                    |
          Phase 1 SQL vertical slice accepted
                    |
       +------------+------------------+
       |                               |
       v                               v
Approved JOINs                 Document ingestion + parser
       |                               |
       |                     cleaning → chunking → embedding
       |                               |
       |                     retrieval → local BGE → citations
       |                               |
       +-------------+-----------------+
                     |
          Reliable conversation + evidence
                     |
            Phase 2 accepted
                     |
            Hybrid A / Hybrid B policy
                     |
           Answer UI + end-to-end release
                     |
            Phase 3 accepted
```

Milestone có thể làm song song BE/FE khi wire contract đã khóa, nhưng **không được** làm JOIN khi relationship contract chưa được kiểm chứng, hay xây Hybrid verdict trước khi SQL/evidence layer ổn định.

---

## 16. Phase 1 — Foundation + Text-to-SQL Vertical Slice

**Mục tiêu:** người dùng Google login → workspace → upload CSV/XLSX → review data → hỏi SQL một bảng → PostgreSQL thực thi đúng → trả bảng/facts/provenance → lưu history. Chưa phát triển RAG hay Hybrid.

### Milestone F1 — Repo, infra cô lập, hợp đồng và oracle

**Phụ thuộc:** Design Approval Gate PASS và lệnh bắt đầu phase từ chủ dự án.

**Nhiệm vụ:**

- [ ] Kiểm tra repo/folder hiện có, tạo hoặc dùng ChatSAR repo độc lập theo chỉ đạo; Git history `main` sạch, `.gitignore`, `AGENTS.md` và file plan tại root.
- [ ] Chọn Python/Node/PostgreSQL/pgvector/Docker image versions sau compatibility review; pin dependencies và commit lockfiles.
- [ ] Tạo minimal FastAPI API + React/Vite web + PostgreSQL Compose; không dựng Langfuse server mới hoặc model host mới.
- [ ] `/live`, `/ready`, `/health`; DB migration cơ bản; CI lint/typecheck/tests/build.
- [ ] Tạo fixture domain A và B có DDL/rows/expected answers; viết **independent SQL oracle** trước khi compiler tồn tại.
- [ ] Tạo benchmark manifest có permissions, inputs, expected results/evidence, negative cases và checksum. Khóa một set held-out ban đầu; không tuning trên set đó.
- [ ] Tạo `docs/CONTRACTS.md`, `docs/CAPABILITIES.md` ngắn nhưng wire-level rõ, không tạo nhiều báo cáo trùng lặp.

**Acceptance:**

- [ ] Compose project/ports/volumes độc lập, không chạm ShopQuery; `web/api/db` healthy; restart không lỗi migrations.
- [ ] CI PASS exact commit, không bỏ qua tests bằng skip ẩn.
- [ ] Fixture/oracle độc lập compiler, có thể chạy và tái hiện expected Decimal/NULL results.
- [ ] `.env.example` không chứa secret thật, cloud disabled, frontend bundle không lộ credentials.

**Không làm:** LLM multi-agent, Langfuse upgrade, bulk model downloads, RAG/embedding.

### Milestone F2 — Google Login + Workspace Ownership

**Phụ thuộc:** F1, OAuth design và credentials được cấp hợp lệ.

**Nhiệm vụ:**

- [ ] Tạo API verify Google ID token và login session + logout + `/api/me`.
- [ ] Xác minh CSRF đúng GIS flow, cookie protections, session expiry, rotation/revoke khi cần, DB-backed sessions.
- [ ] `users`, `sessions`, `workspaces` schema + constraints; Google `sub` unique per provider.
- [ ] FE login/empty state/workspace list/create/select/logout; current principal luôn từ server.
- [ ] Central auth/authorization dependency tại endpoints và tests A/B cùng cross-workspace.

**Acceptance:**

- [ ] Real Google login E2E trong môi trường được cấu hình hợp lệ; nếu chưa có OAuth, tests mock PASS và live `BLOCKED/NOT_RUN` — không được nghiệm thu full F2.
- [ ] Invalid/expired/wrong audience token bị từ chối; logout revoke; duplicate login không tạo duplicate users.
- [ ] A không thể đọc workspace của B; đổi workspace không mang quyền cũ; session persistence theo policy qua restart.

### Milestone F3 — CSV/XLSX Ingestion + Catalog

**Phụ thuộc:** F2 và physical table layout được phê duyệt.

**Nhiệm vụ:**

- [ ] File validation/storage/checksum/jobs, CSV parser và XLSX sheet selection; caps và lỗi thân thiện.
- [ ] Data profiling candidate types/nulls/duplicates/keys/units, preserve Decimal/TEXT ID/timezone.
- [ ] FE upload/preview/review types/keys/grain/approved relation/synonyms, confirm.
- [ ] Atomic publish revision thành physical typed table; catalog mapping IDs; immutable version và provenance.
- [ ] Read-only analytical DB role; indexed access paths cho demo; permission guards.
- [ ] Job resume/fail/idempotent; re-upload same file không tự nhân revision/charge trái phép.

**Acceptance:**

- [ ] CSV có UTF-8 BOM/delimiter/quoted fields và XLSX nhiều sheet được xử lý đúng.
- [ ] `COUNT(*)`, NULL, Decimal, TEXT ID/leading zero và time types khớp row-level oracle sau ingestion.
- [ ] Sai kiểu/corrupt file không silently drop rows; user xem lỗi và quyết định sửa/reupload.
- [ ] Restart/recreate giữ source file, revision/catalog và row count/checksum; A/B owner isolation.

### Milestone F4 — Typed SQL Engine + Chat Vertical Slice

**Phụ thuộc:** F3, Query Plan/Answer contracts đã khóa.

**Nhiệm vụ:**

- [ ] Grounding schema và literals; model proposal adapter mock trước, contract strict.
- [ ] SQLAlchemy Core compiler cho single-table SELECT/filter/count/sum/avg/group/order/limit.
- [ ] Query validation theo G1–G8, permission, DB read-only/timeout/caps; no raw SQL from LLM.
- [ ] Execute PostgreSQL typed rows → Answer Envelope; deterministic renderer SQL đơn giản.
- [ ] Tạo conversation/message/result refs; FE chat/send/history/result tables/source drawer.
- [ ] Gemini và Knowledge adapter contract tests offline; chỉ chạy model-live có budget/permission. Tracing Langfuse tùy compatibility và project đã được phép.
- [ ] Evaluate SQL semantic on dev/regression + held-out đã khóa; báo accuracy/false refusal/per-domain và failure classes.

**Acceptance:**

- [ ] Đủ ít nhất 2 schema khác nhau, các câu SQL một bảng đúng oracle và user-level E2E chạy thật qua browser.
- [ ] Invalid type/table/operator, injection, wrong literal, lost qualifier, COUNT/NULL/Decimal critical cases đạt.
- [ ] Model-live: PASS/FAIL/BLOCKED/NOT_RUN được báo riêng từng provider; không thể gọi model vì 403 thì ghi nguyên nhân, không đổi gate thành mock PASS.
- [ ] Câu trả lời dễ hiểu tiếng Việt, kết quả và provenance không lệch, lịch sử tồn tại sau restart.

### Phase 1 exit gate

- [ ] F1–F4 acceptance có log, commit SHA, source/dataset revisions, failures và test command.
- [ ] Không lỗi critical về permission, SQL silent wrong fact, lost qualifier, datatype hoặc corrupted upload.
- [ ] SQL vertical slice dùng **một** chính thức pipeline. Không phát triển Phase 2 nếu Phase 1 không đủ evidence; ngoại lệ phải được user phê duyệt và giữ blocker công khai.

---

## 17. Phase 2 — Generalized SQL + RAG/BGE + Conversation

**Mục tiêu:** mở JOIN có điều kiện; ingest tài liệu đa định dạng; truy xuất có nguồn bằng embedding + lexical + BGE; follow-up giữ trust/revision.

### Milestone R1 — Approved JOINs và Value Grounding nâng cao

**Phụ thuộc:** Phase 1 accepted.

- [ ] Tạo reviewer UI cho relation cardinality, PK/FK uniqueness, grain và join direction; không tự approve bằng tên cột.
- [ ] Compiler approved 2–3 tables, inner/left join khi phù hợp; aggregation giữ đúng fact grain, fanout guards.
- [ ] Literal candidate mapping có provenance/confirmation; ambiguous year/unit/join paths → clarify.
- [ ] PostgreSQL oracle cho 1:N/N:1, LEFT JOIN, null orphan, missing fact, COUNT, time.
- [ ] Câu SQL multi-table hiển thị source provenance và query result đúng.

**Acceptance:** cross-domain multi-table đúng oracle; không critical fanout, wrong COUNT hay silent value mapping; không thêm regex/domain patches.

### Milestone R2 — Document Ingestion & Embeddings

**Phụ thuộc:** Phase 1 storage/workspace, source revision contract.

- [ ] Tạo document upload/revision/checksum/job/status UI; local TXT/MD/DOCX/PDF text parsers.
- [ ] LlamaParse adapter opt-in cho synthetic hard docs khi được phép; test version/tier/pages/credits; không tự upload internal docs.
- [ ] Normalized doc contract với raw/clean/heading/table/page anchors; parser quality oracle.
- [ ] Structure-aware chunker, source mapping, duplicate prevention; chọn embedding model sau benchmark.
- [ ] pgvector exact retrieval baseline; reindex theo model revision; document ownership filter.
- [ ] Background job/restart recovery không mất file/chunk hoặc chi phí lặp vượt trần.

**Acceptance:** tài liệu mẫu parse đầy đủ, chunks mở nguồn trang/đoạn, embeddings persisted, CPU/GPU usage có đo và owner B không thấy doc A.

### Milestone R3 — Retrieval + BGE + Citation Quality

**Phụ thuộc:** R2 + read-only BGE/GPU inventory PASS.

- [ ] Dense baseline rồi lexical/dense fusion, reranking; không song song nhiều production retrieval pipelines, các cấu hình so sánh nằm trong evaluation harness.
- [ ] BGE local offline load, one instance/process, FP32/FP16/batch/VRAM tests.
- [ ] Evidence selection/adjacent-section expansion; grounded synthesis và citation IDs.
- [ ] Answerability `answered/partial/insufficient` và gold claim-support evaluation.
- [ ] Document source viewer chính xác page/span, unauthorized citation forbidden.
- [ ] Langfuse spans retrieval/rerank/generation với redaction mặc định.

**Acceptance:** Recall@k/citation quality có số đo cho A/B/C, dùng BGE có bằng chứng lợi ích hoặc ghi giới hạn rõ; các critical citation/owner/unknown tests đạt; RAG real E2E chạy qua browser.

### Milestone R4 — Conversation Trust + Multi-source UX

**Phụ thuộc:** R1 và R3.

- [ ] Verified result references giữ query plan, dataset/doc revisions, scope, evidence.
- [ ] Follow-up “tháng trước”, “chỉ quận 3”, “xem chi tiết”, context changes/clarification; không dùng prose chưa xác minh.
- [ ] Stale/failed/partial reference handling; workspace switch không rò chat/results.
- [ ] FE evidence drawer, document manager, progress/job states và error messaging hoàn thiện.
- [ ] Restart/recreate/cancel/retry/incomplete job E2E; no repeated cloud calls on browser retry.

**Acceptance:** follow-up SQL và RAG đúng scope/source; provider failure không biến thành fact; A/B owner isolation, history persistence, browser E2E, no raw traceback.

### Phase 2 exit gate

- [ ] SQL multi-table & RAG E2E trên nhiều schema/docs, independent oracles; embedding/BGE thật có benchmark và tài nguyên/latency được ghi.
- [ ] Parser chọn theo tài liệu, không tự dùng LlamaParse mọi nơi; citation exact source và unknown states được test.
- [ ] Không blocker security, silent corruption, owner leak, document prompt injection critical.

---

## 18. Phase 3 — Hybrid + UX + MVP Release

### Milestone H1 — Hybrid factual và policy grammar

**Phụ thuộc:** Phase 2 accepted.

- [ ] Planner phân biệt SQL facts, RAG evidence và combined tasks; không dùng keyword router theo ngành.
- [ ] Factual Hybrid A kết hợp hai nguồn và giữ scope/time/entity alignment.
- [ ] Policy extraction candidate từ document; source/applicability/unit/effective period check, bounded grammar threshold.
- [ ] SQL evaluation universe với missing facts; deterministic Decimal evaluator PASS/FAIL/UNKNOWN/NOT_APPLICABLE; output selection sau evaluation.
- [ ] Answer Envelope Hybrid, nguồn rule + nguồn facts, tiếng Việt tự nhiên, partial/insufficient khi thiếu một phần.
- [ ] PostgreSQL independent oracle + policy table oracle + source citation gold.

**Acceptance:** tất cả critical policy cases đúng oracle; không missing fact=zero, không sai applicability, không lọc không đạt trước evaluation, không lẫn version/time/unit.

### Milestone H2 — FE polish và demo workflow

**Phụ thuộc:** H1.

- [ ] UI layout sidebar, chat history, dataset/doc selection, evidence drawer, status messages, responsive desktop/mobile cơ bản.
- [ ] Demo scripts gồm SQL, RAG, Hybrid, ambiguous/insufficient, user isolation và restart.
- [ ] UI có khả năng giải thích nguồn/cách tính nhưng người dùng không thấy thuật ngữ lập trình trong câu trả lời thường.
- [ ] Không fake progress hoặc dùng sample hardcoded data làm kết quả thực.
- [ ] Benchmark end-user latency và token/credits cho các demo scenarios; tăng tốc bằng loại bỏ model calls thừa trước khi thêm cache phức tạp.

**Acceptance:** ba demo end-to-end thật trên dữ liệu đã publish, câu trả lời/số liệu/citations hiển thị đúng, không cần sửa tay DB giữa các bước.

### Milestone H3 — Hardening, backup/rollback, release acceptance

**Phụ thuộc:** H2 và các blockers đã xử lý.

- [ ] Security test owner/CSRF/IDOR/prompt injection/upload/SQL injection/unauthorized cloud calls; resource limits và fault tests.
- [ ] Repeat model-live benchmark trong budget; ghi model IDs, SDK revisions, token/credits/latency, false refusals/unknown/critical failures.
- [ ] Docker image pinned digest, reproducible build, no dev hot reload, backend non-root, healthchecks; kiểm tài nguyên GPU/CPU/RAM.
- [ ] Backup database + file artifacts, restore vào environment cô lập, verify checksum/rows/doc citations/permissions/history.
- [ ] Release/rollback runbook, exact commit/image digest, migrations compatibility, data preservation.
- [ ] Dọn unused source/tests/scripts/docs trên chính repo ChatSAR theo call graph; không xóa arbitrary files/volumes/models.
- [ ] Final browser E2E on exact release image và app, không chỉ FE mock.

**Acceptance:** release gates trong Mục 19 đều đạt hoặc ghi blocker rõ; ứng dụng hoạt động độc lập không ảnh hưởng ShopQuery, rollback có test và demo tái lập.

### Phase 3 exit gate

**Release chỉ khi** mọi critical gate PASS, ngưỡng semantic/false refusal/latency/cost đã khóa được đánh giá trên held-out, model-live và real browser E2E đạt, privacy/cloud policy không bị vi phạm, recover/rollback được chứng minh.

---

## 19. Independent benchmark, quality metrics và release gates

### 19.1. Benchmark phải có trước khi implementation

Mỗi case lưu: `case_id`, `domain`, `schema/DDL`, `seed data/rows`, `catalog`, `permissions`, `document revisions/clauses`, `question`, `expected task`, `expected literals/filters/metrics/population`, `expected rows/answer`, `expected evidence`, `expected status`, `source hash` và `oracle methodology`.

Có ít nhất 4–6 schema thật sự khác nhau về naming/cardinality/grain/unit, gồm logistics, khách sạn, thư viện, năng lượng, nông nghiệp và một domain giữ ngoài quá trình tuning. Chia rõ `development`, `regression`, `held-out`. Lock held-out labels/checksums **trước khi model tuning**. Nếu một case held-out bị xem để sửa, case đó mất tư cách held-out và phải thay bằng case chưa nhìn thấy (không sửa gold theo output của model).

Independent PostgreSQL oracle phải do người/logic độc lập viết, không gọi ChatSAR compiler; phép tính Decimal critical có đối chứng riêng. RAG gold được đánh dấu theo claim, document revision, page/offset và coverage; Hybrid gold có population/rule applicability/metric/verdict.

### 19.2. Quy mô khởi đầu đề xuất: 170 cases

| Nhóm | Số case | Chủ đề |
|---|---:|---|
| SQL single-table | 40 | filter/COUNT/SUM/AVG/date/group/order/limit |
| SQL joins, Decimal, NULL, grain | 30 | approved joins, fanout, missing, units |
| SQL ambiguity & negatives | 20 | literal, schema ambiguity, injection, out-of-scope |
| RAG | 40 | retrieval, citations, incomplete/conflict, injection |
| Hybrid | 20 | policy threshold/factual merge, population, rule |
| Conversation & auth/session | 20 | follow-up, revision, history, cross-owner |
| **Tổng** | **170** | **Target ban đầu, chưa phải test đã chạy** |

Đủ positive, negative, paraphrase, unsupported, clarify và metamorphic cases; domain held-out không được dùng để viết prompt. Test counts là tối thiểu đề xuất để bắt đầu, không chạy theo số lượng để che lỗi.

### 19.3. Định nghĩa metrics rõ ràng

- `SQL answer correctness` = số **câu in-scope** trả lời đầy đủ, đúng rows/metrics/scope/oracle ÷ tổng câu in-scope được kiểm. Sai câu, false refusal, trả partial khi thực ra đủ nguồn đều tính không đạt ở metric này.
- `False refusal rate` = số câu in-scope và đủ dữ liệu bị từ chối/unsupported/clarify không cần thiết ÷ tổng câu in-scope đủ dữ liệu.
- `Semantic qualifier coverage` = tỷ lệ raw user qualifiers có biểu diễn đúng trong plan theo gold; phải chấm tập critical riêng, không chỉ model tự khai đã coverage.
- `RAG Recall@k` = tỷ lệ gold evidence (hoặc câu hỏi có gold evidence) xuất hiện trong top-k; cách tính document/chunk/claim granularity khóa trước test.
- `Citation support` = số factual claims được evidence dẫn đúng và đầy đủ ÷ tổng factual claims; human-reviewed/independent labels là chuẩn, LLM judge chỉ phụ trợ.
- `Answer completeness` = tất cả các phần câu hỏi in-scope được trả đủ theo gold.
- `Hybrid verdict accuracy` = đúng PASS/FAIL/UNKNOWN/NOT_APPLICABLE trên toàn evaluation population, không chỉ subset được lọc hiển thị.
- `Latency` = p50/p95 end-to-end theo SQL/RAG/Hybrid và hardware/model configuration; không trộn cached vs uncached.
- `Provider cost` = actual input/output tokens và per-provider charges/credits, với estimated/unavailable được đánh dấu; retries tính vào tổng.
- `Security invariants` = tất cả critical negative tests phải PASS, không average để che cross-owner leak.

### 19.4. Ngưỡng đề xuất để chủ dự án chốt trước held-out

| Gate | Ngưỡng đề xuất | Blocker |
|---|---|---|
| SQL in-scope correctness | ≥95% toàn tập + báo tỷ lệ theo domain | Bất kỳ silent critical wrong qualifier/fanout/Decimal/permission |
| SQL false refusal | ≤3% câu đủ điều kiện | Tăng refusal để né câu khó không được tính thành công |
| RAG supported answer correctness | ≥90% trên corpus có gold và đúng citation | Citation sai owner/bịa nguồn/critical unsupported claim |
| Hybrid policy deterministic critical oracle | 100% trên các policy supported critical cases | Missing fact → zero, sai population/applicability/verdict |
| Security critical tests | 100% PASS | Cross-user leak, arbitrary SQL writes, cloud exfiltration |
| Restart/recreate/persistence critical | 100% PASS | Mất committed data hoặc inaccessible sources |
| Model-live / browser E2E | Phải chạy thật và báo riêng | Chỉ có mock/simulated PASS |
| Latency p95 | **TBD theo hardware inventory + baseline đo trước freeze** | Không công bố target tùy ý trước khi đo |
| Cloud budget | Không vượt trần do user phê duyệt, default 0 | Bất kỳ paid call trái quyền |

Những con số là **threshold proposals**, không phải lời hứa chất lượng hệ thống. Nếu sample nhỏ không hỗ trợ suy diễn mạnh, báo `n`, `n đúng`, per-domain breakdown và confidence/uncertainty; không chỉ báo một tỷ lệ phần trăm làm quảng cáo.

### 19.5. Bốn tầng báo cáo phải tách biệt

1. **Static/unit:** typecheck, lint, pure logic, mock fixtures.
2. **PostgreSQL integration/oracle:** truy vấn và dữ liệu thực trong test DB.
3. **Model/provider live:** model thật, parsing thực và BGE inference; model name/SDK/usage/latency/budget.
4. **Actual browser E2E/release:** frontend + backend + DB + provider được cấu hình, đúng image/revision.

Không ghi “PASSED 1000 tests” thay cho nghiệm thu live. Không ghi “not run because no API key” thành PASS; dùng `BLOCKED/NOT_RUN`.

---

## 20. Risk register và quy trình xử lý lỗi tránh vá lặp

### 20.1. Các rủi ro ưu tiên

| Risk | Dấu hiệu | Biện pháp chính | Chủ nhiệm |
|---|---|---|---|
| Model mất filter/time/selection | SQL chạy nhưng sai ý định | Typed qualifiers + gold semantic cases | Semantic/Query |
| Value mapping sai | “quận 3” thành “3” | Raw→candidate→canonical + provenance | Catalog/Grounding |
| JOIN fanout | SUM nhân nhiều lần | Approved relationships, grain checker, PG oracle | Query/Catalog |
| Missing vs zero | Hybrid loại sai entity | Universe + completeness + UNKNOWN | Hybrid |
| Parser làm mất điều khoản | RAG không thấy ngoại lệ | Source-aware parsing + fidelity benchmark | Documents |
| Retrieval không tìm đúng nguồn | Citation thiếu | Lexical+dense+BGE eval, source revision | Retrieval |
| Langfuse SDK không tương thích | Trace lỗi hoặc không thấy spans | Server inventory + compatibility pin | Infrastructure |
| Knowledge 403 | Model nội bộ không gọi được | DNS/IP/auth check, báo BLOCKED | Providers/Infra |
| GPU OOM | BGE crash/chậm | One instance, batch/precision benchmark | Retrieval/Infra |
| Cloud phí phát sinh | Retry/parser lặp | Hard budget, idempotency/cache | Providers |
| Google owner leak | Đọc source khác owner | Server guards + IDOR negative E2E | Auth |
| CI PASS nhưng demo fail | Mock thay real semantics | Live and actual E2E gates | QA/Release |

### 20.2. Defect workflow (bắt buộc khi lỗi lặp)

1. **Reproduce:** lưu `case_id`, source revision, user/workspace scope giả lập, model/SDK revision, raw user question, result ID, request ID, oracle; redacted logs, không ghi secret.
2. **Classify:** xác định tầng đầu tiên sai: intent, grounding, catalog, compiler, SQL execution, parser, chunk, retrieval, rerank, policy, answer, conversation, auth hoặc UI.
3. **Hypothesis:** nêu nguyên nhân gốc với bằng chứng; không sửa prompt trước khi biết request lỗi kỹ thuật hay semantics.
4. **Bounded remedy:** tối đa một phương án chính + 1–2 controlled experiments; không regex theo câu, không thêm adapter/trình tạo SQL song song.
5. **Regression:** test nguyên lỗi + cross-domain + metamorphic + negative; không sửa oracle để hợp thức hóa output.
6. **Decide:** nếu model fail có hệ thống, khoanh supported scope hoặc đổi chiến lược/provider bằng benchmark; nếu blocker ngoài khả năng, báo BLOCKED và đề xuất lựa chọn phê duyệt.
7. **Clean:** xóa scratch/prototype dead paths sau khi chuyển thành implementation chính, tránh tích lũy duplicates.

### 20.3. Khi nào dừng triển khai

Dừng tại milestone và báo chủ dự án khi: phát hiện rò rỉ cross-owner; query ngoài quyền; tự động chuyển dữ liệu nhạy cảm lên cloud; SQL tạo silent wrong critical result; tính Hybrid missing fact thành fail; không có independent oracle cho chức năng được công bố; model/API contract không tương thích sau bounded experiments; cần migration có nguy cơ mất dữ liệu; cần chạm ShopQuery hoặc nâng cấp shared Langfuse/Knowledge.

---

## 21. Quy tắc báo cáo/commit cho Codex sau mỗi milestone

### 21.1. Không báo cáo “hoàn thành” nếu thiếu bằng chứng

Mỗi milestone report ngắn, theo cấu trúc:

```text
ChatSAR milestone: <F1 / F2 / ...>
Scope approved: <các mục được giao>
Implemented: <đường đi chức năng, tên module/files chính>
Not implemented: <out-of-scope / deferred>
Contracts changed: <NONE hoặc danh sách + approval>
Tests: <command, count PASS/FAIL/SKIP/NOT_RUN, oracle/e2e/live breakdown>
Providers: <Gemini/Knowledge/LlamaParse/BGE/Langfuse/Google status>
Cloud usage: <calls/tokens/credits/cost và permission>
Security: <owner isolation, DB read-only, secret scan>
Persistence/Restart: <trạng thái, checksums nếu có>
Runtime: <Compose services, health, ports, image digest>
Git: <branch, commit SHA, working tree, push/CI URL nếu có>
Bugs/risks: <unresolved blockers, root cause, next action>
Gate: PASS | FAIL | BLOCKED, lý do và evidence refs
```

- Báo số test theo từng loại; không gộp mock với live.
- Chỉ nói đã chạy app ở địa chỉ nào khi kiểm tra HTTP/health thật; không bịa URLs/ports.
- `CI PASS` cần exact SHA thực. Khi chưa push hoặc CI không có, ghi local PASS và CI NOT_RUN.
- Nếu có cloud call, ghi rõ được cấp budget nào và actual usage; không giấu retries.
- Sau một milestone, chủ dự án review trước khi đổi hợp đồng lớn hoặc sang giai đoạn tiếp theo.

### 21.2. Git strategy

- Dùng branch theo tính năng rõ nghĩa, PR nhỏ, exact commit; không push/merge/deploy tràn phạm vi được duyệt.
- Giữ `main` ổn định; nếu user yêu cầu làm trực tiếp trên main thì không tự tạo nhiều nhánh backup/staging.
- Không force push hoặc sửa Git history dự án cũ. Không commit secrets, artifacts/binary lớn, screenshots chứa dữ liệu cá nhân, raw cloud responses nhạy cảm.
- Xóa branch tạm chỉ khi đã merge và có phê duyệt theo workflow; cleanup không được gây mất dữ liệu.

### 21.3. Mẫu Definition of Done cho mọi task

- [ ] Phạm vi được giao và contract không thay đổi ngoài phê duyệt.
- [ ] Mã ngắn, dễ hiểu, có type hints, không code song song/dead code.
- [ ] Có positive + negative tests cho behavior mới; independent oracle cho logic tính toán.
- [ ] Test thực trên dependency liên quan (PG, GPU hoặc provider) nếu được nghiệm thu; nếu chưa chạy đánh dấu rõ.
- [ ] FE/API/states và user messages đúng; security/owner check đầy đủ.
- [ ] Logs/traces redacted; cloud budget/read-only guard PASS.
- [ ] CI/local verification và exact SHA có bằng chứng.
- [ ] Tài liệu vận hành được cập nhật vừa đủ; không tạo report dày vô ích.

---

## 22. Final MVP Definition of Done

- [ ] Google Login thật, logout/session đúng, owner A không thể đọc history/workspace/dataset/doc/result/citation của B.
- [ ] CSV/XLSX upload/profile/review/publish với kiểu/grain/keys/units rõ, source revision immutable và dữ liệu còn qua restart.
- [ ] Text-to-SQL single/multi-table trong phạm vi hỗ trợ đúng PG oracle, read-only, no silent qualifier loss/COUNT/NULL/Decimal/unsafe JOIN.
- [ ] PDF text/DOCX/TXT/MD parse được, source anchors rõ, embedding/index bền vững, BGE local inference thật và retrieval benchmark có báo cáo.
- [ ] RAG citations đúng document revision/page/claim; partial/insufficient khi thiếu bằng chứng, không theo prompt injection trong source.
- [ ] Hybrid factual và policy threshold đúng independent oracle, có phân biệt PASS/FAIL/UNKNOWN/NOT_APPLICABLE và evaluation universe đầy đủ.
- [ ] Conversation follow-up dựa trên verified references, source revisions rõ, không dùng assistant text từ failed/partial answer làm fact.
- [ ] FE sidebar + chat + dataset/doc management + evidence panel, trả lời tự nhiên tiếng Việt không lộ lỗi lập trình; status/loading/progress thật.
- [ ] Gemini/Knowledge/LlamaParse policy phù hợp, compatibility thực đã kiểm hoặc status BLOCKED được xử lý; Langfuse project riêng và usage không lộ dữ liệu nhạy cảm.
- [ ] Docker toàn stack cô lập, health tốt, resource/timeout caps, persistence, backup/restore và rollback có chứng cứ.
- [ ] Security critical PASS; PostgreSQL oracle + RAG/Hybrid gold + model-live + browser E2E + held-out được báo riêng, ngưỡng đã được phê duyệt trước đánh giá.
- [ ] Một implementation chính thức, không thừa source/tests/docs, no dangling legacy code; release commit/image được định danh và tái lập.

**Nếu bất kỳ mục critical nào chưa đạt, trạng thái MVP là `NOT_ACCEPTED` hoặc `BLOCKED`, dù số unit tests lớn.**

---

## 23. Các câu hỏi còn cần quyết định — không hỏi lại những gì user đã cung cấp

| ID | Quyết định cần phê duyệt | Mặc định an toàn |
|---|---|---|
| D1 | Cloud được phép nhận synthetic hay dữ liệu thực nào? | Chỉ synthetic/đã khử nhạy cảm |
| D2 | Cloud budget Gemini/LlamaParse/Knowledge smoke test | 0 đến khi user cho phép; kế hoạch mẫu 10 Gemini calls, 2 file nhỏ |
| D3 | Google OAuth client mới hay dùng client đã có | Client ChatSAR riêng |
| D4 | Có embedding model local phù hợp hay cần cài lần đầu? | Không giả định; kiểm và benchmark |
| D5 | Workspace có cần chia sẻ nhiều users trong MVP không? | Một owner/workspace |
| D6 | Ports/GPU/VRAM/paths, Knowledge protocol/IP, Langfuse version | Read-only inventory rồi khóa |
| D7 | Giới hạn JOIN 2–3 bảng và policy threshold đơn giản | Chấp nhận cho MVP |
| D8 | Thông số hard caps: file size/rows/timeout/credits và latency targets | Benchmark rồi chốt trước release |

**Codex không được tự đặt ngân sách bằng 0 thành số dương hoặc thay scope sản phẩm.** Những điểm chưa duyệt có thể được mock/test offline và báo BLOCKED, không mặc định thực thi cloud.

---

## 24. Nguồn kỹ thuật ưu tiên khi Codex triển khai (kiểm tra lại tại thời điểm dùng)

> Nguồn chính thức xác nhận API/capability; paper cung cấp phương pháp; kết quả benchmark phải đo trên ChatSAR. Không viện dẫn paper để nói hệ thống đã đúng.

**Text-to-SQL / benchmarking**
- Spider: https://aclanthology.org/D18-1425/
- RAT-SQL: https://aclanthology.org/2020.acl-main.677/
- BIRD: https://bird-bench.github.io/
- Spider 2.0: https://proceedings.iclr.cc/paper_files/paper/2025/hash/46c10f6c8ea5aa6f267bcdabcb123f97-Abstract-Conference.html
- PICARD: https://aclanthology.org/2021.emnlp-main.779/
- SQLAlchemy Core: https://docs.sqlalchemy.org/en/20/core/
- SQLGlot (chỉ nếu thật sự cần): https://sqlglot.com/sqlglot.html
- PostgreSQL: https://www.postgresql.org/docs/current/

**RAG / parsing / embedding / reranking**
- ALCE: https://aclanthology.org/2023.emnlp-main.398/
- pgvector: https://github.com/pgvector/pgvector
- Docling chunking: https://docling-project.github.io/docling/concepts/chunking/
- BGE-M3: https://huggingface.co/BAAI/bge-m3
- BGE reranker v2 M3: https://huggingface.co/BAAI/bge-reranker-v2-m3
- LlamaParse Getting Started: https://developers.llamaindex.ai/llamaparse/parse/getting_started/

**Providers / auth / ops**
- Gemini model: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite
- Gemini Structured Output: https://ai.google.dev/gemini-api/docs/structured-output
- Langfuse self-hosted compatibility: https://langfuse.com/self-hosting/upgrade/versioning
- Google ID token verification: https://developers.google.com/identity/gsi/web/guides/verify-google-id-token
- Docker Compose startup order: https://docs.docker.com/compose/how-tos/startup-order/
- OWASP LLM Prompt Injection Prevention: https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html

**Tài liệu khảo sát ngày 29/10/2026**, SDK/provider versions luôn pin dựa trên compatibility và smoke test thực, không lấy snippet cũ làm câu trả lời cuối. Không chạy bất kỳ lệnh remote/cloud nào chỉ để đọc file này.

---

## 25. Lệnh mở đầu khuyến nghị gửi Codex sau khi phê duyệt

> **Không chạy ngay.** Chỉ dùng khi chủ dự án đã duyệt Design Approval Gate và cho phép bắt đầu Phase 1.

> Hãy đọc toàn bộ `Impliment_plan.md`, `ChatSAR_MASTER_PLAN_2026-10-29.md` và `ChatSAR_PROJECT_HANDOFF(1).md` (nếu có), sau đó đọc `AGENTS.md`. Làm đúng kế hoạch MVP, không tự mở rộng công nghệ. Trước tiên chỉ kiểm tra repo, môi trường, Docker ports, dữ liệu, model path, Langfuse version và Knowledge network ở chế độ không phá hủy; trình bày những thông tin nào đã xác minh và thông tin nào còn giả định. Không gọi Gemini/LlamaParse có phí, không tải model mới, không sửa/tắt ShopQuery, không upgrade Langfuse hoặc sửa Google OAuth cũ khi chưa được tôi duyệt. Nếu Design Approval Gate đã được xác nhận đầy đủ, hãy bắt đầu đúng milestone F1, triển khai một vertical slice nhỏ nhất, viết oracle và negative tests trước các tính năng AI, rồi báo cáo theo Mục 21. Dừng ở gate được giao, không tự chuyển sang milestone khác nếu còn critical blockers. Mọi lỗi ngữ nghĩa phải được điều tra nguyên nhân gốc, không vá regex/prompt theo từng câu hỏi; CI PASS không thay model-live và browser E2E.

---

**END OF IMPLEMENTATION PLAN — đây là bản chỉ dẫn triển khai, không phải bằng chứng hệ thống đã xây dựng hay quyền tự động bắt đầu coding.**
