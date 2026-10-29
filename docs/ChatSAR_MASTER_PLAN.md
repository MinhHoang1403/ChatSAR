# ChatSAR — MASTER PROJECT PLAN

**Ngày:** 29/10/2026  
**Trạng thái:** Thiết kế đề xuất — chưa phê duyệt coding/chi phí cloud; không phải chứng cứ phần mềm đã chạy.  
**Đầu vào:** `ChatSAR_PROJECT_HANDOFF(1).md`, trao đổi về Text-to-SQL, RAG, Hybrid, Gemini 3.5 Flash-Lite, Knowledge, BGE reranker, LlamaParse, Langfuse và Google Login.  
**Mục đích:** Một đặc tả triển khai nhất quán cho MVP demo, không xây hệ thống enterprise, không tái sử dụng mặc định source/DB/Docker/phiên đăng nhập của ShopQuery AI.

## 0. Tóm tắt quyết định

**MVP hoàn thành** khi người dùng đăng nhập Google, tạo workspace, upload CSV/XLSX và PDF/DOCX/TXT/MD có kiểm soát, hỏi SQL/RAG/Hybrid giới hạn bằng tiếng Việt, xem kết quả và nguồn, hỏi tiếp, giữ lịch sử sau restart; các bài kiểm thử thực và benchmark đạt ngưỡng đã chốt.

- Kiến trúc: modular monolith; React/TypeScript/Vite + FastAPI/Pydantic + PostgreSQL/pgvector + SQLAlchemy Core + Docker Compose.
- SQL: LLM đề xuất `Typed Query Plan`, backend grounding/binding và biên dịch thành biểu thức SQLAlchemy, không chạy SQL do model tự do tạo.
- RAG: local parsing cho file đơn giản; LlamaParse có điều kiện cho file khó; làm sạch không đổi nghĩa; chunking theo cấu trúc; embedding (cần chọn qua benchmark), hybrid lexical/dense retrieval, BGE reranker-v2-m3 local, trích dẫn tới nguồn nguyên bản.
- Hybrid: loại mô tả (SQL facts + tài liệu giải thích); loại policy threshold đơn giản, evaluator tất định với phân biệt `PASS/FAIL/UNKNOWN/NOT_APPLICABLE`.
- AI: Gemini `gemini-3.5-flash-lite` và Knowledge; một provider được chọn cho mỗi lượt; không ensemble/fallback ngầm. Chỉ bật cloud có budget/permission.
- Theo dõi: tái sử dụng Langfuse server hiện có nhưng project và keys riêng; kiểm tra phiên bản server/SDK trước.
- Auth: Google Identity Services + backend verify ID token + session ChatSAR bằng cookie bảo vệ; `sub` là định danh nhà cung cấp, không dùng email làm khóa.
- Không dùng kiến trúc agent tự động, LangChain/LangGraph, Kubernetes, microservices, Redis/Celery hay nhiều DB nếu chưa có số liệu chứng minh nhu cầu.

### Ràng buộc bất biến

1. LLM output là đề xuất không đáng tin; principal/permission/canonical metadata do server quyết định.
2. Không tự đổi literal (`quận 3` thành `3`), đơn vị, năm, timezone, NULL thành zero hay missing fact thành zero.
3. SQL result không chứng minh model hiểu đúng; citation ID không chứng minh claim được hỗ trợ.
4. Phải giữ raw phrase, grounded value, điều kiện lọc, aggregation grain, order/limit, provenance, source revision.
5. Query chỉ SELECT cho các bảng/quan hệ trong catalog và workspace được phép. Query role ít quyền, timeout, row/result/compute limits.
6. Dùng dataset độc lập theo domain; benchmark/oracle tạo trước implementation, held-out khóa trước tuning.
7. Không động vào project/source/volumes/secrets hiện hành của ShopQuery; chỉ kết nối có phép đến shared provider hoặc Langfuse.
8. Tên production không chứa nhãn giai đoạn kiểu `v1/v2/s1/s2/freeze`; docs kế hoạch có thể có.

## 1. Product requirements và phạm vi

### Đối tượng sử dụng và kịch bản demo

- Người dùng Google login, thấy danh sách workspace và chat của chính mình.
- Tạo workspace; upload CSV/XLSX, xem preview, sửa data types và xác nhận quan hệ; hỏi các thống kê có căn cứ.
- Upload tài liệu PDF text, DOCX, TXT, Markdown; xem trạng thái parse, nội dung và nguồn; hỏi nội dung và thấy trích dẫn đúng trang/đoạn.
- Hỏi câu kết hợp: số liệu theo SQL + giải thích tài liệu, hoặc câu hỏi threshold theo chính sách có đủ điều kiện.
- Hỏi tiếp đổi thời gian/lọc đối tượng mà không phải gõ lại; truy vết được nguồn và cách tính.

### In-scope

- SQL: 1 bảng; count rows/count non-null/count distinct, sum, avg, min/max, group, order, limit, filter AND/OR không nhập nhằng, dates có mốc rõ, JOIN 2–3 bảng có quan hệ được phê duyệt; đơn vị và Decimal.
- Data: CSV UTF-8/BOM, CSV delimiter thường gặp và XLSX nhiều sheet (chọn sheet), mapping tên cột, xác nhận kiểu/khóa/quan hệ, source revision. Lỗi data rõ và có preview trước khi publish.
- RAG: tài liệu vừa phải; trích text có nguồn; retrieval có metadata lọc quyền; rerank; trả lời grounded và partial/insufficient.
- Hybrid: hai loại đã mô tả, policy đơn giản kiểu threshold + đơn vị + metric + population + hiệu lực + applicability, có oracle.
- Conversation: lưu session/chat; tham chiếu typed verified result; đổi scope và hồi phục lỗi; không dùng assistant prose làm fact.

### Out-of-scope ban đầu

- Query SQL tùy ý, DDL/DML, stored procedure, window recursive SQL, 5+ bảng, tự giải nhiều đường JOIN mơ hồ.
- OCR hàng loạt, PDF scan khó/biểu đồ mơ hồ chưa benchmark, live syncing với ERP hay Google Drive.
- Policy pháp lý nhiều tầng, ngoại lệ lồng nhau, suy luận nguyên nhân chỉ dựa vào sự xuất hiện đồng thời.
- Agent tự truy cập internet/thi hành công việc, đa tổ chức/phân quyền phức tạp, workflow approval, realtime data streaming.

### Hạn mức đề xuất để đo và chỉnh trước release (không phải kết quả)

- CSV/XLSX: thử 20 MiB/file, 50.000 rows/sheet; có hard cap backend; nếu vượt giới hạn hiển thị thông báo.
- PDF/DOCX: thử 20 MiB/file, PDF tối đa 50 trang cho cloud demo; file lớn hỏi tách hoặc bật giới hạn khác.
- Truy vấn: default 100 rows/page, hard cap 500 rows, timeout ứng viên 5–10 giây; resource/timeouts thực nghiệm cần đo.
- Một workspace demo ban đầu tối đa vài chục bảng/tài liệu; không cam kết tenant scale lớn.

## 2. Thiết kế frontend (FE)

### Stack và nguyên tắc UI

- React, TypeScript strict, Vite, React Router; một thư viện truy xuất trạng thái server nếu thực sự cần. UI sáng, xanh lam nhẹ, điều hướng sidebar, responsive desktop trước; tránh dashboard quá tải.
- Tất cả business logic và permissions ở backend; FE chỉ là presentation và client validations. Không hiển thị raw stack trace/SQL aliases.
- Người dùng thấy progress thật: `uploading`, `profiling`, `needs_review`, `indexing`, `ready`, `failed`; trạng thái do backend lưu, không giả lập bằng timer.

### Screens

| Screen | Nội dung chính | Tương tác/điểm kiểm thử |
|---|---|---|
| Đăng nhập | Google login, lỗi thân thiện | valid/invalid login, expiry, logout |
| Workspace home | Workspace hiện có, create/select | owner isolation, empty state |
| Chat | Sidebar conversations, central chat, input, dataset/doc scope | send, cancel display, retry rõ, follow-up, history |
| Data | Upload CSV/XLSX, chọn sheet, bảng preview, inferred types, confirm mapping/relation | type review, null, locale, duplicate keys |
| Documents | Upload, parse job progress, list revisions, document viewer | failed parser, retry permission, citation page |
| Evidence panel | Source tab SQL/table/filters; Documents tab with matched excerpt/page | không lộ nội dung không thuộc owner |
| Settings (nhỏ) | Provider status (không lộ keys), usage summary, logout | user-friendly diagnostics |

### Chat layout

- Sidebar: Workspace switcher, New Chat, Chat History, Datasets, Documents, Settings.
- Main: title/scope chips, message list, source links, bảng kết quả, action “Xem cách tính”, ô chat.
- Right drawer (tùy màn hình): bảng kết quả, nguồn tài liệu và trạng thái xác minh. Trên màn hình nhỏ drawer dạng panel mở/đóng.
- Lúc hỏi: hiển thị `Đang hiểu câu hỏi → Đang lấy dữ liệu/tài liệu → Đang tổng hợp`; chỉ hiển thị những bước thực sự xảy ra, không lộ thuật ngữ kỹ thuật cho người dùng thông thường.
- Trạng thái phản hồi: `answered`, `partial`, `insufficient`, `clarify`, `unsupported`, `provider_unavailable`, `execution_error`; copy tiếng Việt riêng và retry có chủ đích.

### FE test

- Google callback/login/session; switching workspace; upload and preview; async progress; chat SQL/RAG/Hybrid; citations navigation; rerender after refresh; API failure; no mixed history; correct thousand separator/decimal; no raw exceptions.

## 3. Backend (BE) và API contract

### Modules (logic, không phải services)

- `auth`: verify login, session revoke, current principal.
- `workspace`: owners/scopes and access guard.
- `datasets`: upload, profile, review, metadata, publish immutable revision.
- `catalog`: schema metadata, columns, approved join edges, units, synonyms.
- `semantics`: task proposal, grounding, clarification, typed plan.
- `query`: SQLAlchemy Core compiler, guards, read-only executor.
- `documents`: upload, parse, normalize, chunk, index, provenance.
- `retrieval`: lexical/vector retrieval, fusion, rerank, evidence.
- `hybrid`: route/evidence plan/policy applicability/evaluation.
- `conversation`: store typed results and trustworthy references.
- `providers`: Gemini, Knowledge, LlamaParse, embedding, BGE (chỉ adapter thực sự cần).
- `observability`: structured events and Langfuse context.

Không tạo `sql_generator_old`, nhiều planner/validator song song hay một generic agent framework.

### API tối thiểu (mô tả, chưa khóa wire-level)

| Method & endpoint | Chức năng |
|---|---|
| `POST /api/auth/google` | nhận credential an toàn; xác minh Google, tạo local session |
| `POST /api/auth/logout` / `GET /api/me` | kết thúc phiên / lấy identity |
| `GET/POST /api/workspaces` | danh sách và tạo workspace |
| `POST /api/workspaces/{id}/datasets` | upload, tạo ingestion job |
| `GET /api/datasets/{id}/preview` | preview dữ liệu theo revision |
| `POST /api/datasets/{id}/confirm` | xác nhận types, keys, mapping, publish |
| `POST /api/workspaces/{id}/documents` | upload tài liệu và parse/index job |
| `GET /api/jobs/{id}` | progress durable của ingest/parse/embed |
| `GET /api/documents/{id}/source` | file/trích đoạn có authorization |
| `GET/POST /api/conversations` | lịch sử/tạo chat |
| `GET /api/conversations/{id}` | messages + evidence refs, owner-checked |
| `POST /api/conversations/{id}/messages` | gửi câu hỏi, đồng bộ request hoặc trả job ref nếu lâu |
| `GET /api/results/{id}` | normalized result/evidence |
| `GET /live`, `/ready`, `/health` | health không gọi provider trả phí |

Lỗi API dùng code công khai ổn định, `request_id`, message tiếng Việt, không gửi exception traceback. Ownership guard bắt buộc ở mọi endpoint nhạy cảm, kể cả download/citation.

### Internal contracts

- `AuthorizedRequest`: principal, workspace, dataset/document revision, question, reference time/timezone, permission snapshot.
- `TaskProposal`: `SQL | RAG | HYBRID | CLARIFY | UNSUPPORTED`, user spans, references, candidate intent, unresolved; untrusted.
- `GroundedQuery`: metric, aggregation, distinct/null semantics, grain, population, input filters, literal provenance, time intervals, approved joins, grouping, selection, sort, limit.
- `EvidencePlan`: SQL source IDs, document revisions, required claims/rule clauses, coverage obligations.
- `QueryExecutionResult`: typed rows, columns, unit, query execution ID, dataset revision, row count, warnings, provenance.
- `DocumentEvidence`: chunk ID, doc ID/revision, page/heading/range, exact excerpt, access scope.
- `PolicyEvaluation`: population, applicability, metric, threshold, unit, effective interval, verdict per entity `PASS | FAIL | UNKNOWN | NOT_APPLICABLE`.
- `AnswerEnvelope`: status, answer facts, display rows, source refs, limitations, user-safe message, request_id.
- `ConversationReference`: `verified_result | reference_only | ineligible`, source revision, plan ID, evidence IDs.

Hợp đồng không buộc mỗi dòng trở thành một class; chỉ tách khi kiểm thử được behavior.

## 4. PostgreSQL, ingestion và ownership

### Lựa chọn storage

- PostgreSQL quản lý người dùng, session hashes, workspace, dataset definitions, schema metadata, upload jobs, document revisions/chunks/embeddings, conversations, messages, results và traces references.
- Các bảng nhập được chuyển thành bảng vật lý theo dataset/revision (được server sinh identifier, không dùng tên người dùng trực tiếp làm SQL identifiers), để giữ kiểu dữ liệu PostgreSQL và phép JOIN có ý nghĩa. Bản nguồn immutable sau khi publish; revision mới thay vì sửa ngầm dữ liệu cũ.
- Catalog map tên dễ hiểu → internal table/column identifiers; mỗi query chỉ bind approved tables in current workspace/revision.
- Schema-per-workspace hoặc per-revision cần prototype cụ thể; không tuyên bố DB role chia tenant hoàn toàn nếu toàn bộ bảng vẫn được một service role đọc được. Backend allowlist và tests cross-workspace là tuyến bảo vệ trọng yếu; RLS cho metadata/chat/chunks khi khả thi; không trông chờ RLS một mình.
- Sử dụng ít nhất app DB role (metadata writes) và SQL query DB role (chỉ SELECT đúng các đối tượng được cho phép); không chạy user queries bằng superuser/migration role.

### Bảng logic tối thiểu

`users`, `sessions`, `workspaces`, `workspace_members` (chỉ nếu cần nhiều thành viên), `datasets`, `dataset_revisions`, `catalog_tables`, `catalog_columns`, `approved_relationships`, `ingestion_jobs`, `documents`, `document_revisions`, `document_chunks`, `conversations`, `messages`, `result_records`, `result_evidence`, `provider_usage`.

Đây là mô hình logic; không cần tạo mọi bảng phụ ngay khi chưa có tính năng sử dụng.

### CSV/XLSX flow

1. Nhận file → kiểm MIME thực, extension, kích thước, zip bomb/path safety; scan khi phù hợp.
2. Lưu original với checksum và scope; tạo ingestion job durable.
3. Parse streaming/chunks theo định dạng; CSV encoding/BOM/delimiter; XLSX sheet selection; tránh thực thi công thức; thông báo cached formula values nếu không đáng tin.
4. Profile: names, type candidates, null counts, sample values chỉ trong quyền được cấp, duplicates, keys candidate, dates/decimal locale, precision.
5. Cho người dùng review type/key/grain/unit/relationship/synonyms, preview expected rows.
6. Publish revision vào bảng vật lý, transaction/atomic readiness; không đánh dấu ready nếu chưa xác nhận integrity.
7. Invalid rows: báo lỗi và cho sửa/reupload; không âm thầm bỏ dòng hay ép kiểu mất giá trị.
8. Restart: jobs recover/dedupe theo checksum+config; giữ idempotency và trạng thái rõ.

### Data quality invariants

- `COUNT(*)` khác `COUNT(col)` và khác `COUNT(DISTINCT col)`.
- `SUM`/AVG dùng NUMERIC/Decimal nếu metric cần chính xác; không ép tiền thành float; integer IDs lưu TEXT giữ zero đầu.
- `NULL`, `no row`, `zero` khác nhau; cần completeness contract trước khi coi no fact là zero.
- Thời gian: ghi rõ timezone dataset; nếu người dùng nói “tháng 9” thiếu năm và context không rõ, hỏi làm rõ; khi dùng datetime ưu tiên `[start, end)` phù hợp semantics.
- Quan hệ approved có cardinality/grain và tests fanout, uniqueness, orphan; không tự JOIN bằng `*id`.

## 5. Text-to-SQL engine

### Cấu trúc đường đi

`question + verified conversation ref → shortlist catalog/value candidates → LLM typed proposal → server grounding/binding → compile SQLAlchemy Core → structural/authorization checks → optional EXPLAIN (no ANALYZE) → read-only execute → evidence/result → answer`.

### LLM proposal

- Một call cho intent+typed task baseline, không bắt buộc dùng hai agents; nghiên cứu staged planning chỉ khi accuracy tăng đáng kể theo benchmark.
- Các trường bắt buộc: current question spans, metric, population, predicates có AND/OR, aggregation, group, joins candidates, selection/order/limit, ambiguity, unresolved.
- Model không sinh permissions, verified flag, canonical mapping chưa có trong catalog.
- Kiểm JSON với Pydantic strict; rejected fields/unsupported operators không tự biến thành SQL khác.

### Grounding

- Chọn metadata theo tên, description, key relationships; nếu catalog nhỏ có thể gửi toàn schema liên quan; không cần embedding/schema vector DB.
- Literal lưu `raw_phrase`, `candidate`, `canonical_value`, `mapping_source`; exact/map-confirmed trước; fuzzy chỉ gợi ý; never silently map `quận 3` to `3`.
- Khi nhiều bảng/metrics tương đương, hoặc thiếu năm/đơn vị, trả `clarify` nếu khác biệt ảnh hưởng kết quả.

### Compiler và validation

- Cho phép SELECT projections/aggregates/filter/group/having/order/limit/approved joins; bind values, whitelist identifiers từ catalog (không bind tên bảng/cột dưới dạng user string).
- Kiểm join graph đúng approved edges, join orientation, cardinality, entity/fact grain, duplicating metrics. Với JOIN gây fanout không chứng minh an toàn thì từ chối hoặc yêu cầu định nghĩa lại grain.
- Query read-only role, transaction read-only, statement timeout, cost/result guards; `EXPLAIN (FORMAT JSON)` chỉ khi cần; **không dùng `EXPLAIN ANALYZE` làm preflight**.
- Trả đúng typed rows (NUMERIC, TEXT, DATE, NULL), metric/unit và execution provenance; không convert TEXT IDs thành numeric.
- SQL runtime có thể phát hiện syntactic/execution errors; không thể chứng minh model đã hiểu toàn bộ intent. Kết quả phải được đối chiếu với oracle qua benchmark.
- Sửa tự động chỉ tối đa một lần cho lỗi kỹ thuật xác định được và có budget; không prompt churn, không đổi plan semantic lặng lẽ.

### Query gates và negative tests

- Reject DDL/DML, UDF gọi tùy ý, system catalog access không được phép, schema lạ, JOIN không approved, non-SELECT và query quá mức.
- Bắt các tình huống mất AND/OR, filter thời gian/khu vực, wrong COUNT, fanout, multi-valued entities, ambiguous units, null/zero, duplicate metrics, string ID và timezone.

## 6. RAG engine: ingestion, retrieval, reranking

### Tài liệu ingestion

1. Upload file, check type/size/authorization, hash, store original/revision.
2. Chọn parser theo loại và chất lượng: TXT/MD direct; DOCX local; PDF text local PyMuPDF; LlamaParse khi file khó và cloud allowed. Docling là phương án local để benchmark nếu cần.
3. Parse ra normalized document: raw/clean text, headings, tables, page numbers, page text spans, offsets, parser/version/status, checksum.
4. Clean an toàn: Unicode, whitespace, line wrapping, header/footer repeat có xác nhận; không loại mất phủ định, số, đơn vị, ngữ cảnh heading.
5. Structure-aware chunking: heading/paragraph/list/table trước, tokenizer-aware sau; thử 350–600 token, overlap chỉ khi cần; row table gắn header/caption, source ID bất biến.
6. Embedding: chọn model đa ngôn ngữ dựa benchmark; BGE-M3 là ứng viên 1024 chiều; không nhầm với BGE reranker. Giữ model revision/dimension/normalization trong metadata; khi đổi model phải reindex có kiểm soát.
7. pgvector store + metadata scope; indexes theo corpus thực, bắt đầu exact vector search (nhỏ) trước HNSW; có thể đo ANN khi scale.
8. Job states durable, parsing cache theo content checksum + parser/version/options; tránh cloud charging lặp.

### Retrieval

1. Query reformulation chỉ từ câu hiện tại + verified context; không dùng trợ lý nói ở lượt trước làm fact.
2. Workspace/doc revision filter trước candidate retrieval, không lấy cross-owner rồi mới lọc ở UI.
3. Dense top-k thử 20; lexical keyword top-k thử 20 (chú ý xử lý tiếng Việt, IDs và stemming); kết hợp RRF/dedup trong phạm vi đã lọc.
4. Rerank bằng local `BAAI/bge-reranker-v2-m3` trên ~10–20 candidates, batch thử 4/8, `max_length` theo model/docs và benchmark; không xem rerank score như xác suất claim đúng.
5. Evidence selection 4–6 chunks, mở rộng adjacent chunk/page khi bảng/quy định bị cắt; bảo đảm citation tới raw source/revision.
6. LLM synthesis chỉ dùng supplied evidence; check citation ID membership, owner scope, claim support/completeness theo test; partial/insufficient nếu không đủ.

### BGE deployment

- Xác minh model local path hiện hữu (người dùng viết AAI; model card chuẩn `BAAI/bge-reranker-v2-m3`), permissions và checksum; không tự download/cache mới.
- Kiểm PyTorch/CUDA/VRAM; một model instance, tránh nhiều uvicorn workers mỗi worker nạp model.
- Baseline FP32; đo FP16, latency/VRAM/ranking drift, batch/length, GPU contention; xác định rõ fallback khi không có GPU.
- Không biến service BGE riêng trừ khi hiệu năng/recovery cần.

### Retrieval benchmark

- Gold evidence theo doc ID/revision/page/section/claim, không chỉ text similarity.
- Các config A: dense; B: dense+lexical; C: dense+lexical+BGE. Đo Recall@k, MRR/nDCG nếu phù hợp, citation support, answer completeness, p50/p95, VRAM, cost.
- Positive, negative (câu không có câu trả lời), contradictory docs, multi-page table, missing exceptions, prompt injection, wrong revisions, bilingual Vietnamese/English.

## 7. Hybrid engine

### Mode A: Factual join

- Câu hỏi gồm metric SQL + giải thích tài liệu. Planner phân biệt nguồn định lượng và nguồn mô tả; execute SQL/retrieve docs với cùng scope/revisions; join theo key/time/document context được chứng minh; answer không biến correlational description thành proven causation.

### Mode B: Policy evaluation

- Bắt đầu grammar: `metric`, `operator`, `threshold`, `unit`, `population`, `applicability`, `validity_interval`, `source_clause`, `missing_data_policy`.
- Retrieve policy → check quote/source/version/validity → bind metric/table/grain → enumerate evaluation population → compute per-entity facts → evaluate with Decimal/typed comparison → verdict `PASS|FAIL|UNKNOWN|NOT_APPLICABLE` → output selection → natural answer.
- Không trộn `evaluation_population`, `input_predicate`, `policy_applicability` và `output_selection`.
- Nếu thiếu fact hoặc chưa có completeness contract, verdict UNKNOWN, không tự zero; multiple clauses/exceptions/nested applicability nằm ngoài MVP.
- Deterministic evaluator unit tests, independent policy oracle và unseen coverage tests.

## 8. Provider integrations

### Gemini

- SDK `google-genai`; `gemini-3.5-flash-lite` có Structured Outputs theo model card. Tài liệu 29/10/2026 dùng Interactions API `client.interactions.create(... response_format={type:text,mime_type:application/json,schema:...})`, nhưng phải smoke test chính model+SDK+schema trên account trước khóa; giữ một đường API được nghiệm thu, không trộn nhiều interface trong production.
- Strict Pydantic validation ở backend; structured JSON ≠ semantic correctness. temperature, max tokens và support controls thử sau xác nhận.
- No auto model switch; retry tạm thời có cap/backoff và tính budget; 400/401/403 không retry như transient.
- Usage lấy từ provider khi có, ghi model ID, request ID, token, status/latency; tuyệt đối không đưa API key vào trace.

### Knowledge

- Base URL + model `knowledge`; protocol OpenAI-compatible chỉ là giả định cần test; IP/network allowlist và auth kiểm tra từ backend container (đã có tiền lệ HTTP 403 ở dự án khác).
- Probe chỉ sau khi được phép: health/reachability, simple completion, valid JSON, capability supported, token usage, timeout/concurrency.
- Chọn one default provider sau model semantic benchmark; provider khác chỉ fallback nếu user/admin bật rõ. No silent ensemble.

### LlamaParse

- SDK hiện tại `llama-cloud` / `LlamaCloud`, env `LLAMA_CLOUD_API_KEY`; parse API tier-based. Baseline `cost_effective` nếu cần markdown; `fast` không có markdown; agentic khi bảng phức tạp có bằng chứng.
- Upload/job/parse/result và usage credits; cap file pages, per-job credits, retry policy, cache local theo hash+config. Không gửi dữ liệu nội bộ tới cloud nếu chưa cho phép.
- Pin version/tier sau smoke test; tránh `latest` vô thời hạn.

### Langfuse

- Dùng server hiện có nhưng project/API keys ChatSAR riêng. Verify server version read-only: Python SDK v4 cần server >=3.63 (v3) hoặc v4; SDK v5 cần server >=4.59. Không nâng cấp Langfuse đang dùng bởi ShopQuery.
- Root trace per chat request, child spans cho task grounding, SQL execution, retrieval/rerank, generation/evidence; không tạo spans giả. Inputs/output theo policy redaction: default lưu IDs/status/timings/token/cost, không raw PII/secret/raw docs.
- Langfuse là observability, không là source of truth cho chat hay budget enforcement.

### Google login

- Google Identity Services web client; backend verify ID token signature, issuer, audience, expiry, nonce/CSRF theo flow. Dùng Google `sub` liên kết `users`, email là profile phụ, không làm primary key.
- Backend tạo/revoke session độc lập ChatSAR; cookie HttpOnly/Secure/SameSite phù hợp và CSRF protection; logout, expiry, restore after restart, rate limiting.
- Source data, chat, documents và citations đều có owner/workspace authorization; test cross-user/cross-workspace cả endpoints download/retrieval.
- OAuth client riêng cho ChatSAR với đúng JS origins/redirect; không yêu cầu Gmail/Drive scopes chỉ để login.

### Unified config keys (minh họa, không có secret thật)

`APP_ENV`, `DATABASE_URL`, `SESSION_SECRET`, `GOOGLE_CLIENT_ID`, `GEMINI_ENABLED`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `KNOWLEDGE_ENABLED`, `KNOWLEDGE_BASE_URL`, `KNOWLEDGE_API_KEY`, `KNOWLEDGE_MODEL`, `LLAMAPARSE_ENABLED`, `LLAMA_CLOUD_API_KEY`, `LLAMAPARSE_TIER`, `RERANKER_MODEL_PATH`, `RERANKER_DEVICE`, `EMBEDDING_MODEL_PATH`, `LANGFUSE_ENABLED`, `LANGFUSE_BASE_URL`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `CLOUD_CALLS_ALLOWED`, `CLOUD_MAX_REQUESTS`, `CLOUD_BUDGET_USD`.

Khóa provider bắt buộc chỉ khi bật; secrets inject runtime, không commit. Cloud policy `false` và budget `0` mặc định, được enforce tại backend. Budget counters phải persist/durable. Timeouts theo từng provider độc lập. Cần circuit/bounded retry gọn, không framework lớn.

## 9. Answer rendering và conversation semantics

### Answer envelope

- `status`: `answered | partial | insufficient | clarify | unsupported | provider_unavailable | execution_error`.
- `facts`: numeric/display rows, unit, metric, filters, timezone, revision, provenance.
- `citations`: typed links với doc ID/revision/position/permission; citation SQL dùng dataset/revision/query result provenance.
- `limitations`: missing evidence, missing entities, unsupported clauses.
- `trace_id`/`request_id` internal, chỉ hiển thị mã hỗ trợ khi cần.
- UI dùng tiếng Việt rõ ràng: “Theo dữ liệu ... có ...”, “Tôi chưa đủ thông tin để kết luận ...”. Không in SQL exception/JSON/alias.

### Naturalization strategy

- SQL count/table đơn giản: template deterministic → tránh call model và tránh model đổi số.
- RAG/Hybrid: model chỉ diễn đạt grounded facts/evidence; đầu ra kiểm số liệu, citation IDs, entity/status và completeness trước khi gửi.
- Follow-up: chọn `verified_result` và typed plan của lượt trước, không lấy lời kể của assistant làm truth. Stale revision yêu cầu re-run/notification; partial/failed premise không được tự nâng lên verified.

## 10. Docker, vận hành, dữ liệu và an toàn

### Compose

- `web`: React production build + nginx reverse proxy `/api`, không có API secrets.
- `api`: FastAPI, non-root, một worker ban đầu khi BGE nằm trong process; health endpoints không gọi cloud.
- `db`: PostgreSQL/pgvector, persistent volume độc lập, migrations.
- `worker`: chỉ thêm khi ingestion/embedding cần durable background processing; nếu có, ưu tiên DB-backed jobs, không bắt buộc Redis/Celery.
- BGE cache chỉ đọc; files volume upload/read-write riêng; không mount ShopQuery DB/volumes.
- `depends_on: condition: service_healthy`, resource limits, restart policies, Docker build pinned bases/deps, no `latest` on release.

### Ops

- `/live`: process alive; `/ready`: essential DB/migrations ready; `/health`: dependency status không gọi provider trả tiền.
- Backup logical DB + file artifacts + manifests; định kỳ restore thử vào môi trường cô lập; restore verify checksums và row counts. Không sao lưu secret thô vào Git.
- Rollback: pin image digest+schema migration compatibility; bảo vệ active+rollback, không `docker system prune --volumes` trên máy có ShopQuery.
- Logs structured, request IDs, PII redaction, bounded retention, no secrets.
- Security upload: type validation, zipbomb limits, sanitization, prompt-injection treatment, no SSRF from arbitrary document links; CSV export formula injection mitigation.

## 11. Tổ chức repository

```text
ChatSAR/
├── backend/
│   ├── app/
│   │   ├── api/ auth/ workspace/ catalog/ datasets/
│   │   ├── semantics/ query/ documents/ retrieval/
│   │   ├── hybrid/ conversation/ providers/ observability/
│   ├── migrations/
│   └── tests/
├── frontend/
├── evaluations/
│   ├── datasets/
│   ├── oracles/
│   └── harness/
├── infra/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── CAPABILITIES.md
│   ├── CONTRACTS.md
│   ├── TEST_PLAN.md
│   └── OPERATIONS.md
├── compose.yaml
├── .env.example
├── AGENTS.md
└── README.md
```

Đây là sơ đồ đích; chỉ tạo module khi xuất hiện use case. Không nhân bản fixtures/tests/docs; source rõ trách nhiệm, type hints, comments có ích; một implementation chính thức. Không đặt tên mã source theo phase/version.

## 12. Benchmark độc lập và tiêu chí chấp nhận

### Dataset strategy

- Dựng 4–6 domain độc lập (logistics, khách sạn, thư viện, năng lượng, nông nghiệp, 1 domain held-out), khác nhau thật về join/grain/naming/units.
- Mỗi case giữ DDL, rows, tài liệu/policy, permissions, câu hỏi tiếng Việt, expected SQL-independent results, evidence và output status.
- Dùng independent PostgreSQL oracle do người benchmark viết, Decimal manual oracle cho critical metrics; không sinh gold từ compiler/proposal của ChatSAR.
- Tách development, regression và held-out theo schema/domain, khóa checksum/labels trước tuning; case bị nhìn thấy trở thành regression, không được gọi held-out nữa.
- Có positive/negative/unsupported/ambiguous/follow-up/metamorphic/paraphrase variants.

### Kích cỡ và ngưỡng đề xuất trước benchmark (chỉ là TARGET)

| Test group | Cases dự kiến | Target nghiệm thu |
|---|---:|---|
| SQL single table | 40 | End-to-end correctness ≥95% trong in-scope |
| SQL joins/NULL/date/Decimal | 30 | Không critical regression; domain checks |
| SQL ambiguous/negative | 20 | Không thực thi khi thiếu điều kiện quyết định |
| RAG retrieval/answers | 40 | Recall/evidence và citation được đánh giá riêng; target answer correctness ≥90% |
| Hybrid policy/factual | 20 | 100% deterministic policy oracle critical |
| Conversation/session | 20 | 100% security/cross-user critical |
| **Tổng** | **170** | Test mock ≠ model-live; PASS/FAIL/SKIP/NOT_RUN tách biệt |

Các tỷ lệ chỉ là mục tiêu đề xuất, không phải số liệu đã đo. Cần khóa cách tính accuracy denominator (supported questions, answered wrong, false refusal), per-domain minimum, confidence interval/độ lớn mẫu và latency/cost gates trước khi xem held-out. Refusal sai không được tính là PASS. Critical blocker: silent wrong qualifier, cross-owner leak, silent wrong Decimal/NULL/Join, policy verdict thiếu bằng chứng, citation sai owner.

### Test pyramid

1. Static/format/lint/typecheck/dependency/license checks.
2. Unit: typed contracts, date math, Decimal, join cardinality, verdict evaluation, scope guarding.
3. PostgreSQL integration: real catalog/materialized tables/role permissions/oracle.
4. Mock provider: error shapes, timeout, empty result, invalid JSON, credits cap, restart jobs.
5. Model-live bounded: Gemini and Knowledge same dataset; keep provider/model/SDK/version/latency/tokens/cost separate.
6. RAG live: actual parse/embed/BGE/query/citation; compare baseline dense vs fusion vs rerank.
7. Browser E2E: login, upload, ask, citation, history, changed dataset, retry/error.
8. Deployment: Compose healthy/restart/recreate, persistence, restore, exact image, rollback, isolation ShopQuery.

### Root cause policy

- Capture failure with request ID, exact scope, model version, plan, source revisions, oracle, repro.
- Diagnose stage: intent/grounding/schema/SQL compiler/execution/retrieval/evidence/answer/UI/auth.
- Fix at owning layer; regression test; cross-domain/metamorphic retest; do not patch by domain name/regex.
- Bounded trials; repeated model semantic failure → limit support or change provider/strategy based on measured data, not endless prompt tweaking.

## 13. Ba giai đoạn có deliverables và gates

### Phase 1 — Foundation + Text-to-SQL vertical slice

**Phải làm:** research/approval, repo+Compose isolated, Google login, workspace, CSV/XLSX upload/profile/review/publish, catalog, strict typed query plan, Gemini/Knowledge provider test adapters (cloud disabled except approved tests), SQLAlchemy compiler/read-only PG, result envelope, small chat UI, independent SQL oracle, basic Langfuse instrumentation.

**Không làm:** RAG docs/chunk/vector/BGE, policy engine, agents.

**Deliverable:** user login → workspace → upload table → question SQL (one table + defined aggregation) → actual PG rows + provenance → natural UI; live model results separately measured; tests on >=2 different schemas; restart persistence.

**Gate:** all security/correctness critical PASS; semantic in-scope threshold for tested set; actual browser E2E; CI exact commit; cloud usage recorded; no unresolved critical errors.

### Phase 2 — Generalized SQL + RAG/BGE + Conversation

**Phải làm:** approved 2–3 table join, value grounding and nullable/grain hardening; PDF/DOCX/TXT ingestion + local/LlamaParse parser selection, structure-aware chunk, embedding/pgvector, lexical+dense retrieval, BGE local GPU, citation/answerability, trusted follow-up, Langfuse detailed spans.

**Deliverable:** SQL multi-table + RAG real documents across domains; evidence panel; provider cost/latency comparison and job recovery.

**Gate:** SQL oracle for joins/date/COUNT/NULL; RAG gold evidence/citation + correct insufficiency; reranker contribution measured; permissions/restart/model-live/browser E2E PASS.

### Phase 3 — Hybrid + UX completion + MVP release

**Phải làm:** hybrid A SQL+doc facts, hybrid B simple threshold policy grammar and deterministic eval, unified answer renderer, demo scripts and dataset, UI polish, security/fault testing, backup/restore, runbook, dependency/image pinning/cleanup/rollback.

**Deliverable:** reproducible SQL/RAG/Hybrid demo using independent datasets, full history, natural Vietnamese answers and source explanations.

**Gate:** policy population completeness and verdict oracle, E2E, false refusal and answer correctness thresholds, cost/latency/cap limits, no critical leak/silent corruption, backup recovery, release image checksum, CI on release commit.

## 14. Trình tự triển khai tránh làm lại

**Before coding: Design Approval Gate**

1. Khóa capability matrix/out-of-scope và benchmark data/oracle.
2. Khóa semantic contracts/authority và error states.
3. Chọn data physical storage revision policy và user/owner isolation.
4. Inventory in read-only mode: hardware/CUDA, model path/version, Knowledge network/auth/spec, Gemini model access, LlamaParse subscription limits, Langfuse server/SDK compatibility, Google OAuth clients/allowed origins, Docker ports/resources.
5. Khóa công nghệ/versions, cloud policy/budget và acceptance criteria.

**During coding:** chia task theo vertical slice nhỏ và kiểm thử thật cuối mỗi milestone. Codex không tự nâng provider, tự tạo agent, thêm DB/Redis hoặc sửa project cũ khi chưa có ADR và quyền.

**After acceptance:** review source/tests/doc ownership; xóa code thử nghiệm không dùng nhưng không hủy dữ liệu; publish commit/image digest; giữ rollback; kiểm thực tế exact deployment.

## 15. Quyết định người dùng cần xác nhận (không hỏi lại các dữ kiện đã cho)

| ID | Cần xác nhận | Mặc định đề xuất |
|---|---|---|
| D1 | Có được dùng dữ liệu thực hay chỉ synthetic cho Gemini/LlamaParse? | Chỉ synthetic/đã khử nhạy cảm |
| D2 | Google OAuth client tạo mới hay có thể thêm ChatSAR origin vào client hiện hữu? | Tạo client riêng để cô lập |
| D3 | Budget cho smoke tests Gemini/LlamaParse/Knowledge? | 0 cho đến được duyệt; đề xuất 10 Gemini, ≤2 small docs |
| D4 | Máy có embedding model local chưa? | Không giả định; chọn qua benchmark |
| D5 | Workspace có cần chia sẻ giữa nhiều user ngay MVP? | Mỗi workspace một owner; chia sẻ để sau |
| D6 | Chính xác ports, GPU VRAM, Langfuse version, Knowledge protocol/IP | Inventory read-only trước code |
| D7 | Có chấp nhận giới hạn policy threshold đơn giản và join 2–3 bảng? | Có, để MVP nghiệm thu được |

## 16. Nguồn kỹ thuật và nghiên cứu (đọc 29/10/2026)

- Spider 2018: https://aclanthology.org/D18-1425/
- BIRD: https://bird-bench.github.io/
- Spider 2.0: https://proceedings.iclr.cc/paper_files/paper/2025/hash/46c10f6c8ea5aa6f267bcdabcb123f97-Abstract-Conference.html
- RAT-SQL: https://aclanthology.org/2020.acl-main.677/
- PICARD: https://aclanthology.org/2021.emnlp-main.779/
- ALCE: https://aclanthology.org/2023.emnlp-main.398/
- PostgreSQL current (18): https://www.postgresql.org/docs/current/
- SQLAlchemy Core: https://docs.sqlalchemy.org/en/20/core/
- SQLGlot: https://sqlglot.com/sqlglot.html
- Google Gemini model info: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite
- Gemini structured output: https://ai.google.dev/gemini-api/docs/structured-output
- BGE reranker official: https://github.com/FlagOpen/FlagEmbedding/blob/master/examples/inference/reranker/README.md
- BGE-M3 embedding: https://github.com/FlagOpen/FlagEmbedding/blob/master/research/BGE_M3/README.md
- Docling chunking: https://docling-project.github.io/docling/concepts/chunking/
- pgvector: https://github.com/pgvector/pgvector
- LlamaParse SDK: https://developers.llamaindex.ai/llamaparse/parse/getting_started/
- LlamaParse pricing/tiers: https://developers.llamaindex.ai/llamaparse/general/pricing/
- Langfuse versions: https://langfuse.com/self-hosting/upgrade/versioning
- Langfuse instrumentation: https://langfuse.com/docs/observability/sdk/instrumentation
- Google token verification: https://developers.google.com/identity/gsi/web/guides/verify-google-id-token
- Docker Compose health/dependencies: https://docs.docker.com/compose/how-tos/startup-order/

**Diễn giải bằng chứng:** tài liệu chính thức xác nhận tính năng/API và những giới hạn đã công bố; benchmark/paper gợi ý phương pháp; **chỉ** thực nghiệm ChatSAR mới chứng minh performance/accuracy của cấu hình cụ thể. Mọi threshold, số lượng calls, giới hạn tệp, số cases, số token/chunk ở trên đều là **giá trị đề xuất**, cần được chốt trước khi thử held-out, không phải thành tích đã đạt.

## 17. Definition of Done cho toàn MVP

- [ ] Người dùng đăng nhập Google, logout, xem đúng lịch sử/workspace, không thể truy cập owner khác.
- [ ] CSV/XLSX tạo được dataset revision có metadata, review trước publish, tồn tại sau restart.
- [ ] SQL một/multi-table trong phạm vi hỗ trợ trả số liệu đúng oracle, SQL read-only và safe.
- [ ] PDF/DOCX/TXT parse có nguồn, chunks, embeddings; retrieval và BGE reranker hoạt động thật.
- [ ] RAG dẫn đúng source/revision/page và nói thiếu dữ liệu khi chưa có bằng chứng.
- [ ] Hybrid A/B có kiểm soát policy/fact/population, không đoán missing = zero.
- [ ] Follow-up dựa trên verified references, không dùng partial/error làm nguồn sự thật.
- [ ] Câu trả lời tự nhiên tiếng Việt, không lộ exception/SQL aliases, bảng/nguồn hiển thị rõ.
- [ ] Gemini/Knowledge/LlamaParse usage có budget; Langfuse traces không tiết lộ secrets/PII.
- [ ] Docker isolated, healthy, persistence, backup/restore, release/rollback đã kiểm thử.
- [ ] Static + PG oracle + live provider + browser E2E + held-out riêng; tất cả blocker critical được giải quyết.
- [ ] Không có code path parallel/legacy, không ảnh hưởng ShopQuery AI.

**Quy tắc cuối:** Không bắt đầu xây dựng chỉ vì kế hoạch đã viết xong. Cần người dùng phê duyệt scope, budget và Design Approval Gate trước khi giao prompt Codex/code/Docker.
