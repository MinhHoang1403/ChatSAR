# Bằng chứng triển khai Giai đoạn 1

## Natural Answers, SQL Transparency & Final UX — 30/10/2026

### A. Tổng quan

**NOT_ACCEPTED.** Phần độc lập đã triển khai và kiểm thử, chưa đủ điều kiện READY_FOR_USER_ACCEPTANCE. Baseline `32ffde9`, working tree sạch. Không generation mới hoặc sửa .env/quota/ledger. Báo cáo này là trạng thái hiện hành; các mục bên dưới giữ làm lịch sử.

Đã sửa prose còn kỹ thuật, thiếu SQL theo message, lỗi thiếu stage, pending checkpoint bị hiểu nhầm hoàn tất, sidebar/composer và hai nút chi tiết. Bổ sung regression internal column ID: kiểm trước khi thay gạch dưới, ưu tiên alias xác nhận. Lỗi model lịch sử/canary candidate chưa được xác minh sửa live.

### B. Text-to-SQL

Một đường production: question → catalog xác nhận → QueryPlan → binder/compiler SQLAlchemy Core → PostgreSQL reader → facts → composer tất định. QueryRequest chỉ candidate offline. AST `INSTRUCTIONS`, `generate_proposal`, `request_client`, `reserve_call`, `finish_call`, `compile_query` khớp baseline. Parser/setup/publish/tracing không đổi. Chỉ thêm thời gian SQL và checkpoint trước execute, không thêm engine/grammar/dependency.

Canary **BLOCKED**; semantic mới **0/90 đã đo,90 BLOCKED**. Không có accuracy/false refusal/held-out/latency model mới. Baseline lịch sử22/26: in-scope16/19=84.21%, negative6/7=85.71%, false refusal2/19=10.53%;64/90 chưa đo, chưa đạt95%. Một answered output thiếu projection dù số trùng vẫn FAIL. Lookup→SUM/mất mã, MIN→top, timestamp/Boolean condition, FX status còn cần canary và đo lại; chưa chứng minh hết silent critical wrong answers. Composer không sửa được plan hiểu sai câu hỏi.

Latency lịch sử19 attempts HTTP p50/p95=2170.08/5856.69ms, provider2108.47/5783.25ms; SQL17 samples3.72/51.51ms. Không phải SLA browser/bản mới. Maintenance MIN đã dùng phát triển, không còn blind held-out. Printing thay thế6 scenarios (5SQL/1clarify) giữ khóa;5 gold SQL PASS, model BLOCKED. Không gọi fixtures tự viết là benchmark mù bên thứ ba.

### C. Natural Answers

Không LLM viết lại. Decimal thành chuỗi exact/dấu phẩy thập phân, không float/rounding; typed rows/TEXT zero đầu/NULL/0 giữ nguyên. Chỉ lấy alias/tên/unit xác nhận, không suy filename/description/grain. COUNT_ROWS nói bản ghi, không tự gọi vận đơn/phòng/thiết bị; MIN/MAX không bịa người thắng. Prose lookup tối đa4 cột, bảng giữ đủ projection.

Ví dụ fixtures offline, không phải model-live mới:

| Dạng | Trước | Sau |
|---|---|---|
| SUM | Nhãn kỹ thuật:10.10 | Tổng phí trong dữ liệu đã chọn là10,10VND |
| COUNT_ROWS | Nhãn phép đếm | Có0 bản ghi trong dữ liệu đã chọn; không suy entity |
| MIN | Nhãn phép tính | Giá trị nhỏ nhất của phí … là10,10VND |
| Lookup | Chỉ bảng | Bản ghi phù hợp … có Mã vận đơn:0007; phí:10,10VND; bảng đủ cột |
| Grouping | Nhãn khó đọc | Dưới đây là tổng phí theo từng nhóm Mã vận đơn …; số ở bảng |
| NULL/empty/partial | Dễ nhầm zero/đủ dữ liệu | NULL không phải0; empty khác aggregate NULL; partial báo chưa đầy đủ |

20 unit cases đối chiếu ý nghĩa/exact values, số vượt JS safe integer, âm/scale/mã/internal ID; expected không do composer sinh. Thiếu alias thì tên nguồn có thể vẫn tiếng Anh, không tự dịch/bịa metadata.

### D. SQL & Source UI

Processing additive owner-scoped lưu dataset/revision/checksum/timezone/grain, actual provider/model khi có bằng chứng dispatch, stage/error code và parameterized SQL từ chính Select dùng execute. Không literal_binds/raw bind values; không gửi SQL/rows/secrets vào public trace. Mỗi message/result có evidence riêng; ownerB đọc404. GET/reload/panel không gọi model/compile/execute lại.

Hai nút answer: Nguồn & xử lý / Xem SQL; lỗi: Chi tiết lỗi / SQL-status phù hợp. Đóng mặc định, một panel/message; Escape đóng/trả focus. SQL format chỉ thêm whitespace, giữ quoted identifiers/literals/placeholders; monospace/cuộn ngang. Lịch sử cũ thiếu SQL báo “Câu lệnh SQL của lượt trả lời này chưa được lưu.”, không dựng lại. SQL mới có API/PG/SSR/restart proof; positive browser model→SQL mới **BLOCKED**, không nâng mock thành E2E PASS.

Model latency từ reply/error thật; SQL duration chỉ execute+fetch; backend sau kiểm quyền/trước final persistence, không phải browser latency. Thiếu số liệu không giả0. Stages authorization/catalog/provider_preparation/provider_call/proposal_parse/semantic_validation/sql_compilation/execution/composition/persistence/retrieval. Validation/build Select còn chung bước semantic, không bịa số đo riêng.

Checkpoint trước execute giữ SQL khi final persist lỗi; final transaction atomic. Pending chặn trùng/xóa, poll chỉ đọc. Restart chuyển SQL in_progress thành unknown, không replay/giả failed. Checkpoint không lưu được thì không execute. Composition lỗi sau SQL giữ SQL succeeded, không bịa answer. Lỗi trước message trả diagnostics an toàn, không tạo lịch sử giả.

### E. Frontend và browser

Tinh chỉnh UI hiện hữu: new chat+··· chung nhóm, workspace selector duy nhất trên search; plusmenu3icons/3tác vụ thật; model selector gọn, giữ pill. Không đổi core/profile/history/CRUD/Setup/Google.

Browser đợt này **24/27 PASS,3 BLOCKED**, không tái dùng26/28 cũ. PASS: (1) nhóm newchat/menu; (2) selector trên search; (3) workspace/history switch; (4) hotel lịch sử300.15; (5) hai nút đóng mặc định; (6) actual model metadata cũ; (7) SQL cũ chưa lưu; (8) một panel; (9) Escape/focus; (10) tạo chat private/error HTTP thật; (11) controls pending; (12) source/stage/no-provider đúng; (13) SQL chưa tạo; (14) switch/Escape panel mới; (15) reload evidence; (16) plusmenu3icons; (17) Data Manager mở/đóng; (18) history menu Escape; (19) profile mở/hủy; (20–23) widths1440/1280/768/390 không tràn ngang; (24) console không error. BLOCKED: fresh Google login, hai tài khoản browser độc lập, model thật mới→natural answer+compiled SQL panel. Existing session/API ownership không thay hai flow Google thật.

Giữ chat demo “Kiểm tra nguồn và SQL — tổng amount?” trong “Kiểm thử lịch sử 30-10”: source private từ chối trước generation, provider_preparation/DATA_PERMISSION_REQUIRED, SQL chưa tạo, nguồn không đổi. Không xóa dữ liệu khác. Ảnh natural-menu.jpg/natural-mobile-error.jpg/natural-final-error.jpg local ignored; reset viewport, giữ tab localhost.

### F. Tests

| Nhóm | Tổng | PASS | FAIL | BLOCKED | NOT_RUN |
|---|---:|---:|---:|---:|---:|
| Backend unit |143|143|0|0|0|
| Integration API/PG, provider mock |33|33|0|0|0|
| SQL oracle |25|25|0|0|0|
| Semantic gold SQL |75|75|0|0|0|
| Gold thay thế |5|5|0|0|0|
| Evaluation/reader/quota/scorer |21|21|0|0|0|
| Semantic model-live mới |90|0|0|90|0|
| Negative/context, nhóm con90 |15|0|0|15|0|
| Gemini candidate canary |1|0|0|1|0|
| Natural answers, nhóm con unit |20|20|0|0|0|
| SQL provenance, nhóm con integration |3|3|0|0|0|
| Error diagnostics, nhóm con integration |4|4|0|0|0|
| Frontend SSR/DTO |12|12|0|0|0|
| Browser |27|24|0|3|0|
| Security, nhóm con12unit+8integration+6reader |26|26|0|0|0|
| Secret scan tracked/served bundle |1 audit|1|0|0|0|
| Persistence HTTP/PG/restart |1 luồng|1|0|0|0|

Không cộng trùng nhóm con; provenance/error có overlap. Diagnostics gồm11 biến thể trong1test và execution/clarify/persistence ở3test khác. Persistence dùng UUID harness riêng, patch provider chỉ trong process test trả typed plan; compile/reader/PG/HTTP/result/restart thật, SUM0.30→prose0,30 và SQL/history khớp trước/sau. Không inject browser cookie, không gọi đó model-live.

Ruff/format/mypy18modules, TypeScript/build, runtime, prepare-only fidelity đạt. Starlette/httpx có1 deprecation warning, không skip. Bằng chứng: CI/tests; artifacts/natural-final-audit.json, natural-usage-audit.json, natural-acceptance-prepare.json local ignored.18 app modules source/container hash khớp, hai plan và gold/manifest/checksums giữ byte baseline.

### G. Usage

Ledger đầu/cuối63=Gemini58/Knowledge5; mới0/0, LlamaParse/BGE0. Baseline quyền13=8/5, đã dùng50 Gemini bổ sung. Riêng50 lượt trong grant bổ sung: known tokens68810input/15050output/0thought, estimate0.0582680USD, reserve0.6671498USD. Toàn ledger63: known tokens81973input/20570output/0thought, estimate đã biết0.0655169USD, tổng reserve0.7764988USD (không phải hóa đơn hoặc chi phí đầy đủ khi còn usage thiếu). HTTP400 `d10d5f23-d15d-4c9e-8e21-37e67b510b1c`: dispatch1, usage/costNULL, reserve0.0137353USD, PROVIDER_SCHEMA. Không suy unknown thành miễn phí.

Đọc PG/Langfuse trace `974e3f15543b1b415e25f9fb3c8e5837` chỉ xác nhận400/BadRequestError/schema_complexity=false, thuộc tính schema lỗi cụ thể UNKNOWN. Không interaction ID/billing account access; store=false không chứng minh charge0. Guard thật trả USAGE_UNKNOWN trước insert/network, count không đổi. Không tạo reconciliation record/quota exception thiếu chứng cứ/quyền riêng. Còn trần45Codex/50tổng, giữ5 cho chủ dự án, **không dispatch được hiện tại**. Không sửa .env/keys/flags/global budget/grant/ledger.

### H. GitHub/Docker

feature/sql-foundation, PR1 Draft/open; không merge/main/Phase2. Milestones `3cf87697acd3ca200063b0fc0783ee34aa0a5ad8`, `7009bd44097454cb594b8a3aac3bcc55ddcd1ac6` đã push; CI push+PR PASS: [7009 push](https://github.com/MinhHoang1403/ChatSAR/actions/runs/41012923751), [7009 PR](https://github.com/MinhHoang1403/ChatSAR/actions/runs/41012932688). Commit chốt nhãn/báo cáo kiểm CI exact HEAD và local/remote SHA trong bàn giao cuối. [PR1](https://github.com/MinhHoang1403/ChatSAR/pull/1). Main giữ c05f26b1a301e91e8ea6ddaadedb0e1ed03b735d.

Một Compose chatsar, web/api/db healthy; volumes chatsar_database/chatsar_uploads giữ nguyên;7 migrations foundation/identity/datasets/conversation/catalog/provider_grants/chat_management, không migration mới. Không stack/dọn dự án khác. Secret scan103 tracked files và served JS/CSS không trùng keys/passwords local; .env/artifacts ignored, ảnh/PII không public. Không force/prune volumes.

### I. Kết luận và checklist UI

**NOT_ACCEPTED.** GateA BLOCKED; B deterministic PASS nhưng model E2E thiếu; C backend/persistence/SSR PASS nhưng positive browser mới BLOCKED; D đạt phần đã kiểm; E offline/infrastructure PASS, fresh Google/two-account proof thiếu; F chờ chủ dự án. Không Giai đoạn2.

1. Mở http://localhost:18181, Google login/logout/login thủ công. Hai phiên Google độc lập không thấy workspace/chat/source/profile/result của nhau.
2. “Nghiệm thu giao diện 30-10”→“Tổng tiền phòng?” vẫn300.15; hai nút đóng mặc định, SQL cũ báo chưa lưu, không dựng/gọi model lại.
3. “Kiểm thử lịch sử 30-10”→chat demo nguồn/SQL: đúng tên file/thiếu quyền/stage; SQL chưa tạo; một panel, Escape đóng; reload vẫn còn, nguồn không đổi.
4. Dấu+ mở upload/tạo workspace/Data Manager; local review/publish kiểm TEXT zero đầu/Decimal/NULL; hồ sơ/hủy/rename/history hoạt động. Chỉ xóa chat test tự chọn, giữ lịch sử thật.
5. Chưa gửi thêm AI Setup/chat cloud khi USAGE_UNKNOWN. Sau đối soát/quyền hợp lệ cần canary, benchmark và positive browser mới để nghiệm thu natural prose/source/model/timings/SQL. Không cần scripts/DB/raw JSON cho nghiệm thu UI.

---

## Hoàn thiện chất lượng và giao diện — 30/10/2026

### A. Tổng quan

**NOT_ACCEPTED.** UI và các API quản lý chat/hồ sơ đã triển khai, kiểm browser thật và PostgreSQL; phần độc lập đã hoàn tất. Gate Text-to-SQL/model-live còn BLOCKED_USAGE_UNKNOWN. Không dùng UI PASS, mock hoặc oracle để thay nghiệm thu model. Giữ PR1 Draft, không merge/main hoặc Giai đoạn 2. Baseline đầu tác vụ cf882a2 sạch; ledger63 (58 Gemini/5 Knowledge). Không thêm generation trong tác vụ này.

### B. Nghiên cứu và quyết định

Nguồn/so sánh đầy đủ ở DECISIONS và CONTRACTS. RESDSQL hỗ trợ tách dạng truy vấn và schema linking; RAT-SQL nhấn mạnh liên kết metadata; BIRD nhấn mạnh giá trị nguồn/kiến thức thiếu; Spider2 cho thấy giới hạn khi ngoại suy benchmark. Không triển khai model/framework của các paper. Google structured output chỉ bảo đảm cấu trúc, có giới hạn recursion/branching và vẫn cần validation. WAI-ARIA làm căn cứ focus/menu/Escape; Google GIS là căn cứ origin/client/nonce, không nới bảo vệ.

Candidate offline QueryRequest phân biệt record/list/list_all/scalar/group/ranking, kiểm projection cần có và identifier từ catalog, chuyển danh sách condition hậu thứ tự sang Predicate hiện hữu. Kiểm tree/depth/caps/Boolean operands, không bù filter thiếu. Phương án không chọn: anyOf đệ quy đã HTTP400; regex theo ngành; LLM loops/engine thứ hai. Schema candidate3422 bytes so với production3260 bytes khi chưa gắn catalog; không suy số byte thành token/latency/accuracy. Chi phí vẫn một lượt nếu được canary, nhưng chưa có số đo thật. Hai-stage fixture comparison chỉ kiểm internal structure (1 accept/7 reject), không chứng minh model quality.

**Gate tương thích chưa đạt:** giữ candidate/tests offline; generate_proposal và INSTRUCTIONS production trở về đúng hợp đồng đã chạy thành công. Không có flag hoặc runtime cạnh tranh. AST của quota/dispatch/finish_call cũng không đổi. Cần canary hợp lệ trước đổi wire runtime, không ship contract unproven để đạt tiến độ. Compiler/query.py, parser/tabular.py, setup.py, datasets.py và observability.py giữ nguyên byte, hai plan và gold/checksum gốc không đổi.

### C. Text-to-SQL

Runtime vẫn question→grounded catalog→QueryPlan→binder/compiler SQLAlchemy Core→reader PostgreSQL→facts/answer tất định. Candidate không phải compiler hoặc đường SQL thứ hai. Guard không chứng minh mọi qualifier tiếng Việt; candidate chưa chứng minh giảm false refusal hoặc hết silent wrong answer.

| Lỗi ban đầu | Xử lý có căn cứ | Trạng thái nghiệm thu |
|---|---|---|
| Lookup mã+phí thành SUM, mất mã | Candidate record/direct projection, required_columns và identifier catalog; regression trên shipment/asset/book | Offline đạt; chưa live, runtime cũ vẫn có lỗi đã đo |
| MIN bị gắn top thiếu order | Candidate scalar tự bounded, ranking riêng cần order; MIN hours/weight/temperature | Offline đạt; chưa live |
| COUNT+SUM thiếu timestamp/AND rỗng | Candidate condition tree không nhận AND rỗng/orphan/cycle/shared; bảo toàn hai mốc và hai metrics được khai | Offline đạt biểu diễn; chưa chứng minh model không bỏ qualifier/chọn sai COUNT |
| Thiếu FX trả unsupported | Candidate fixture clarify không thực thi/không tự đổi tỷ giá; chỉ dẫn runtime cũ giữ an toàn | Chưa chứng minh model phân loại đúng, giữ lỗi lịch sử |

Không có semantic accuracy mới trên runtime bàn giao (0 model calls). Baseline lịch sử22/26: in-scope16/19 (84.21%), negative6/7 (85.71%), false refusal2/19 (10.53%), một answered plan/output mismatch dù số trùng. Chưa thấy sai giá trị trong17 answers cũ đã execute không phải bằng chứng zero risk.64/90 cũ chưa đo; không tuyên bố90PASS hoặc đạt95%. Candidate cần chấm toàn bộ bộ thích hợp sau canary, không tái dùng điểm cũ.

Latency lịch sử19 in-scope attempts: HTTP p50/p95=2170.08/5856.69ms; provider2108.47/5783.25ms; SQL17 samples3.72/51.51ms (nearest rank). Không là browser SLA/runtime mới. Không có token/cost/latency/held-out score mới. Maintenance MIN cũ đã được dùng phát triển, không còn blind held-out. Bộ thay thế printing khóa trước model run:6 scenarios,5 SQL gold đạt,1 clarify; model NOT_RUN. Người tạo biết labels, không gọi benchmark mù bên thứ ba.

### D. UI/API và browser

Trước: sidebar phẳng, logoC/tagline, composer nhiều hàng, fallback checkbox, refresh/history helper. Sau: chữ ChatSAR, sidebar thu gọn; new chat và menu hide/delete all; history nhóm theo revision có nhóm legacy; mỗi chat menu đổi tên/xóa, rename Save/Cancel; account menu/hồ sơ local; thin header/source; pill một hàng +/textarea/Gemini-Knowledge/send. Enter gửi, Shift+Enter xuống dòng và auto-grow, chặn trùng/pending. Dấu+ nối upload/workspace/Data Manager thật. AI model mặc định Gemini, controls chọn model thu gọn, consent giữ nguyên. Không ping provider, không fallback checkbox/helper dài. Kết quả có evidence mở rộng; nhãn đọc được, không sửa Decimal/NULL/TEXT values.

API thêm PATCH/DELETE conversations, DELETE workspace conversations, GET/PATCH profile; migration additive chat_management thêm phone/interests/revision binding, backfill lịch sử một nguồn. Session/CSRF/owner bắt buộc; khóa workspace serialize send/delete, pending409; transaction results→messages→chat. Xóa lặp an toàn, giữ dữ liệu nguồn/workspace/provider ledger. Profile ChatSAR không sửa Google, không gửi preferences lên prompt/trace. UI cancel bỏ draft, lỗi trong dialog hiển thị được, đóng dialog bị chặn khi mutation đang chạy.

Browser thật28 scenarios:26PASS/2BLOCKED (artifacts/quality-browser.json). Đã kiểm session hiện hữu, workspace, nhóm nguồn, hide/restore giữ active300.15, collapse, menu/focus/Escape, rename lưu/khôi phục giữ messages, profile đọc/lưu/khôi phục/hủy, plus tạo workspace/upload/local review/publish, privacy guard, Enter/ShiftEnter, pending, chọn model không ping, bốn widths, restart/history, single delete và bulk delete. Hai Google flow độc lập/fresh login chưa kiểm lại; session hiện hữu không thay fresh-login proof. API A/B vẫn PASS. Không automate Google auth dialog hoặc inject cookie.

Chủ dự án xác nhận xóa đúng hai chat tổng hợp trong workspace kiểm thử. Browser thực hiện single rồi bulk; DB chứng minh test_chats0, test_source_ready1 (2rows), workspace1, original_acceptance_chats2, hotel result300.15 còn1, orphan messages/results0, ledger63. Không xóa lịch sử khác. Screenshots chỉ local ignored, không public PII. Width390/768/1280/1440 đều scrollWidth=viewport; pill khoảng52–54px khi một dòng, mobile menu truy cập được. Đây là QA theo kịch bản, không chứng nhận WCAG toàn diện.

### E. Kiểm thử

| Hạng mục | Tổng | PASS | FAIL | BLOCKED | NOT_RUN |
|---|---:|---:|---:|---:|---:|
| Backend unit |123|123|0|0|0|
| API/PostgreSQL integration, provider mock |28|28|0|0|0|
| SQL oracle gốc |25|25|0|0|0|
| Semantic gold SQL cũ |75|75|0|0|0|
| Gold thay thế |5|5|0|0|0|
| Evaluation tests (reader/quota/scorer…) |21|21|0|0|0|
| Semantic model-live trên bản bàn giao |90|0|0|90|0|
| Negative NL, nhóm con90 |10|0|0|10|0|
| Provider candidate adapter mock, nhóm con unit |2|2|0|0|0|
| Candidate compatibility Gemini-live |1 canary|0|0|1|0|
| Frontend SSR/DTO |10|10|0|0|0|
| Browser E2E |28|26|0|2|0|
| Auth/security, nhóm con (12unit+8integration+6reader) |26|26|0|0|0|
| Docker/HTTP persistence |1 luồng|1|0|0|0|

Không cộng nhóm con thành test độc lập; mới tăng unit gồm15 planning và2 adapter candidate. Integration thêm profile+3 chat CRUD/race; frontend thêm grouping và exact-value label. Ruff/format/mypy16 modules, TypeScript/production build đạt. Một deprecation Starlette/httpx, không skip. Runtime/prepare-only fidelity hotel/maintenance/logistics/library, persistence/restart đạt, không generation. Test concurrency giữ pending trong provider mock rồi thử delete/bulk/send kháckey đều409, chỉ một dispatch mock.

### F. Usage và blocker

Baseline grant13=Gemini8/Knowledge5; đầu và cuối tác vụ này63=58/5. Toàn grant đã dùng50 Gemini mới, tác vụ này0; Knowledge/LlamaParse/BGE mới0. Known tokens68810input/15050output/0thought, known estimate0.0582680USD; reserve0.6671498USD. HTTP400 d10d5f23-d15d-4c9e-8e21-37e67b510b1c vẫn usage/costNULL, dispatch1, reserve0.0137353USD; không coi miễn phí. Quota còn45Codex/50tổng về trần quyền, nhưng không dispatch được.

Đã đọc lại PG và Langfuse trace974e3f15543b1b415e25f9fb3c8e5837: HTTP400/BadRequestError, schema_complexity=false; thuộc tính schema lỗi chính xác UNKNOWN. Không provider interaction ID/usage do phản hồi lỗi, store=false; API key không cấp quyền billing. Docs Google chỉ chỉ đường logs/AI Studio/Cloud Billing, không chứng minh charge0 theo request. Không tạo reconciliation record khi thiếu chứng cứ; audit riêng quality-usage-audit.json giữ BLOCKED. Kiểm guard grant thật trả USAGE_UNKNOWN trước insert/network, count63 không đổi. Không sửa .env/keys/flags/ledger/grant trong tác vụ này.

### G. Docker/GitHub

Một Compose chatsar, web/api/db healthy; volumes chatsar_database/chatsar_uploads giữ nguyên.7 migrations gồm chat_management; chạy lại additive migration an toàn. Langfuse hiện hữu đọc metadata thành công, không tạo stack khác. Main giữ c05f26b1a301e91e8ea6ddaadedb0e1ed03b735d. Feature/sql-foundation và PR1 Draft/open; SHA/CI exact-head báo trong bàn giao và GitHub. Source milestone cceb455 và a33d21d đã push/CI push+PR PASS; commit sau cùng giữ provider compatibility gate và báo cáo này. Secret scan tracked/changed/staged và assets trước push; .env/artifacts ignored. Không force/merge/prune volumes hoặc tác động ShopQuery. Ảnh cũ giữ rollback, không tự dọn tài nguyên chưa đủ căn cứ.

### H. Nghiệm thu và checklist cho chủ dự án

**NOT_ACCEPTED:** UI/API đủ để kiểm thử trực tiếp, nhưng không hạ gate SQL/model-live. Cần chứng cứ usage/billing thực hoặc quyết định riêng rõ ràng của chủ dự án; không tự bypass. Cần chủ dự án thực hiện Google fresh login và hai phiên Google độc lập. Không tự sang Giai đoạn 2.

1. Mở localhost:18181, đăng nhập Google thủ công; đúng tài khoản/workspace, không lỗi origin.
2. Dấu+ → tạo workspace/tải CSV/XLSX; kiểm sheet, TEXT zero đầu, Decimal/NULL; local review luôn dùng được.
3. AI Setup/chat cloud hiện bị chặn; chưa thử thêm để nghiệm thu model khi chưa đối soát. Đọc lại hotel300.15 trong workspace nghiệm thu không phát sinh cloud.
4. Confirm/publish rồi chọn source: hiện đúng filename, revision giữ nhất quán với lịch sử. Đổi source của chat cũ cần chat mới.
5. Chat mới: composer một hàng; Enter gửi, Shift+Enter xuống dòng; đang xử lý không gửi trùng. Private chưa cấp quyền phải báo rõ, không gửi provider.
6. Mở nguồn/cách tính; kiểm giá trị và điều kiện. Đổi tên giữ messages; hủy không đổi; hide/restore giữ chat active.
7. Xóa single/bulk chỉ trên chat test được phép; xác nhận phải nói đúng workspace, nguồn vẫn còn. Hai luồng đã kiểm bằng browser+DB.
8. Account → hồ sơ: lưu hiện lại sau reload; hủy bỏ draft; Google profile giữ nguyên. Đăng xuất rồi đăng nhập thủ công lại.
9. Hai tài khoản độc lập: không thấy workspace/chat/profile/source/result của nhau. Báo lỗi dễ đọc, không cần script/DB/raw JSON.

---

## Kết quả ổn định cuối ngày 30/10/2026

### A. Tổng quan và gates

**NOT_ACCEPTED — chưa đủ điều kiện READY_FOR_USER_ACCEPTANCE.** AI Smart Data Setup và hai SQL smoke đã hoạt động thật; chất lượng benchmark chưa đạt mục tiêu, 64/90 tình huống chưa được đo trên cấu hình cuối. Model-live hiện **BLOCKED_USAGE_UNKNOWN** theo điều kiện dừng của chủ dự án. Không merge main, không sang Giai đoạn 2.

| Gate | Kết quả | Bằng chứng và giới hạn |
|---|---|---|
| A Backend/security | PASS | Unit/integration/reader/owner/CSRF/session, không mất dữ liệu |
| B Smart Setup | PASS trong phạm vi đã kiểm | 2 lượt Gemini hotel được backend chấp nhận, có review/publish/source fidelity/restart; đề xuất nguy hiểm bị chặn offline |
| C Text-to-SQL | FAIL chất lượng; live BLOCKED | In-scope 16/19, negative status 6/7; 4 ca không đạt; không suy thành accuracy 90 ca |
| D Frontend | 18/20 browser scenarios PASS, 2 BLOCKED | Fresh Google login và hai tài khoản độc lập chưa làm lại; unit/build và các luồng CSV/XLSX/chat/source/restart đã kiểm browser thật |
| E Infrastructure | Local PASS; CI theo exact commit báo cuối | web/api/db healthy, 2 volumes giữ nguyên, Langfuse đọc trace thật, secrets scan trước push |

### B. AI Smart Data Setup

Nguyên nhân cụ thể của lượt hotel cũ vẫn **UNKNOWN**: phản hồi trước đã mất, không thể quy lỗi chính xác cho model hay validator. Các lỗi xác minh độc lập đã sửa: model phải sao chép toàn bộ cấu hình kỹ thuật cột; validator kiểm candidate key từng cột làm từ chối nhầm khóa ghép hợp lệ. SetupSuggestion chỉ chứa metadata/thay đổi theo column ID; backend giữ cấu trúc nguồn, defaults NULL, order/name/checksum/revision, ghép thành SetupProposal rồi dùng validate_rows chính thức. Uniqueness khóa ghép kiểm trên toàn tuple. Không có validator thứ hai, không bỏ leading-zero/Decimal/NULL/mapping/type checks.

Phản hồi thêm issues với code/rule/column_id/position/data_type/decision/message. Đề xuất nguy hiểm rejected và fallback local; đơn vị chưa xác nhận/ngày mơ hồ needs_review. Mọi đề xuất vẫn chờ owner confirm, không auto publish. UI giữ thống kê NULL/empty/duplicate của preview khi áp dụng proposal; lỗi mất cảnh báo ô trống đã tái hiện và có regression.

Live: hotel Setup 1 qua HTTP harness và 1 qua browser đều mode=ai_proposal, toàn bảng/metadata/typed rows đúng trước publish; room_charge trống thành NULL theo review, booking_ref TEXT giữ nguyên, source checksum bất biến. CLI kiểm setup response đã lưu còn nguyên sau restart. Browser review/publish có thể xem trong workspace nghiệm thu riêng. Knowledge quota chặn trước network cho bài UI local fallback: mode=local/CALL_LIMIT_REACHED, nguồn vẫn needs_review; Knowledge ledger không tăng. Lỗi JSON/provider timeout/403 và restart pending được kiểm offline/integration, không giả là live outage test.

### C. Text-to-SQL, quality và latency

Pipeline giữ nguyên: question → grounded catalog → Gemini typed proposal → validation → SQLAlchemy Core → PostgreSQL reader → verified facts → deterministic Vietnamese answer. Sửa có căn cứ: hướng dẫn scalar aggregate không tự thêm GROUP BY/projection, schema provider enum IDs từ catalog đã kiểm quyền và raw_user_spans nguyên văn câu hỏi do server biết. Không nới compiler/owner/literal/coverage checks, không raw SQL, retry loop hoặc JOIN.

Thí nghiệm tách Predicate thành anyOf để chặn AND rỗng ở provider **FAIL tương thích**: lượt đầu HTTP 400/BadRequestError, code PROVIDER_SCHEMA, trace `974e3f15543b1b415e25f9fb3c8e5837`; schema_complexity=false trong chẩn đoán, không biết chính xác thuộc tính gây lỗi. Không có usage; đã dừng live, loại thí nghiệm và phục hồi **toàn bộ 15 app modules đúng byte của 92580c71cef6eff6978a90edfcf919de68acebd3**. Local/container fingerprints khớp; không reset ledger hoặc đổi trạng thái lỗi. Frontend giữ bản sửa thống kê. Không để code provider bị từ chối trong runtime.

Hai SQL smoke cấu hình đã khôi phục: hotel SUM room_charge **300.15**, maintenance SUM labor_hours **2.50**, đúng cột/operator, không thêm filter/group/projection; provenance/checksum và lịch sử sau restart đã xác minh. Browser hotel hiển thị 300.15 thật, không tính thêm một lần benchmark độc lập cho cùng ca.

| Bộ đo trên hợp đồng cuối | Đã chạy | PASS | FAIL | Chưa đo sau điều kiện dừng |
|---|---:|---:|---:|---:|
| 90 scenarios đã khóa | 26 | 22 | 4 | 64 BLOCKED |
| In-scope, nhóm con | 19 | 16 (84.21%) | 3 | Không ngoại suy |
| Negative/status, nhóm con | 7 | 6 (85.71%) | 1 | Không ngoại suy |
| Maintenance held-out, nhóm con | 5 | 4 | 1 | Không dùng ca FAIL để tuning |

In-scope false refusal **2/19 (10.53%)**. Chấm bảo thủ có **1 answered plan/output mismatch**, vẫn là FAIL dù số phí trùng; chưa thấy sai giá trị số trong 17 answers đã thực thi của tập cuối, không coi đó là zero risk hoặc đạt critical gate. Negative status đối chiếu exact gold, đồng thời kiểm plan/task và không có rows; chưa có full contextual/owner/revision model benchmark. Per-domain: logistics 14/17, hotel 2/2, energy 1/1, library 1/1, maintenance 4/5. Agriculture/follow-up/metamorphic NL chưa nghiệm thu; 75 gold SQL checks chỉ là oracle tất định.

| Ca FAIL còn lại | Nguyên nhân được quan sát | Xử lý |
|---|---|---|
| basic_logistics_text_id | Model dùng SUM(fee), chỉ trả 10.10; gold yêu cầu projection mã 0007 và phí | Số phí đúng nhưng thiếu cột/sai dạng plan; giữ FAIL, không sửa gold/câu hỏi |
| basic_maintenance_minimum | MIN đúng cột nhưng result_mode=top không order | Guard trả clarify; false refusal, không tuning trên held-out |
| paraphrase_08 | AND không children, COUNT_NON_NULL thay COUNT_ROWS; thiếu khoảng timestamp | Guard chặn trước SQL; thí nghiệm grammar bị HTTP400 đã loại, chưa sửa được live |
| negative_05 | Trả unsupported trong khi gold là clarify do thiếu tỷ giá | Không execute/đoán đơn vị; vẫn FAIL status |

Scorer ban đầu không nhận scalar COUNT(DISTINCT col)+IS_NOT_NULL cùng col tương đương gold. Đã chứng minh trên PostgreSQL độc lập, thêm regression và chấm lại response đã lưu không thêm cloud; không thay expected. Không áp dụng equivalence này cho COUNT_ROWS/GROUP BY/OR hoặc cột khác. Runtime không đổi vì sửa scorer.

HTTP latency của **19 in-scope attempts**: p50 **2170.08 ms**, p95 **5856.69 ms** (nearest rank, gồm 2 refusal). Provider tương ứng p50 **2108.47 ms**, p95 **5783.25 ms**. PostgreSQL execution **17 samples**: p50 **3.72 ms**, p95 **51.51 ms**. Không phải browser end-to-end p95 hoặc SLA release. Stage timings hiện có catalog/provider/validation (gồm compile)/execution/composition/server_processing; chưa tách độc lập prompt generation và compile, không bịa thời gian cho hai bước đó.

### D. Hồi quy cuối

| Nhóm | Tổng | PASS | FAIL | BLOCKED | NOT_RUN |
|---|---:|---:|---:|---:|---:|
| Backend unit | 106 | 106 | 0 | 0 | 0 |
| PostgreSQL/API integration, provider mock | 24 | 24 | 0 | 0 | 0 |
| SQL oracle bất biến | 25 | 25 | 0 | 0 | 0 |
| Semantic gold SQL checks | 75 | 75 | 0 | 0 | 0 |
| Manifest/Decimal/reader/quota/scorer/acceptance tests | 21 | 21 | 0 | 0 | 0 |
| Semantic model scenarios cấu hình cuối | 90 | 22 | 4 | 64 | 0 |
| Gemini transport/schema, toàn đợt, không phải semantic accuracy | 50 | 49 | 1 | 0 | 0 |
| Negative/status, nhóm con của 90 | 10 | 6 | 1 | 3 | 0 |
| Frontend SSR/DTO | 8 | 8 | 0 | 0 | 0 |
| Browser scenarios | 20 | 18 | 0 | 2 | 0 |
| Auth unit/integration + reader, nhóm con | 25 | 25 | 0 | 0 | 0 |
| Docker/HTTP persistence | 1 luồng | 1 | 0 | 0 | 0 |

Không cộng nhóm con thành tổng test độc lập. Unit tăng 94→106: 11 ca Setup/regression đa nguồn và 1 contract catalog schema. Evaluations 14→21: 2 quota/concurrency, 4 scoring semantics, 1 SQL aggregate equivalence. Frontend 7→8: giữ thống kê preview khi merge proposal. Lint/format/mypy 15 modules, frontend TypeScript/production build đều PASS; một cảnh báo deprecation Starlette/httpx, không skip. Hai plan và fixtures/gold/checksum khóa không đổi.

### E. Usage, quota và điều kiện dừng

Baseline PostgreSQL 30/10/2026 **02:17:55 UTC (09:17:55 giờ Việt Nam)**: tổng 13 reservations, Gemini 8/Knowledge 5. Cuối đợt: tổng **63**, Gemini **58**, Knowledge **5**; tăng **50 Gemini requests**, 0 Knowledge/LlamaParse/BGE. Mọi request mới có dispatch_count=1; 49 có response/usage hợp lệ, lượt cuối xác minh HTTP400 bằng Langfuse. Guard chặn retry thứ hai trước transport; không suy số HTTP lịch sử trước guard từ reservations cũ.

Usage đã biết: **68,810 input / 15,050 output / 0 thought tokens**; estimated cost **0.0582680 USD**, tổng reserve **0.6671498 USD**. Lượt cuối thiếu usage/cost, vẫn tính một request và giữ reserve **0.0137353 USD**; tổng tiền thực không xác định. Không gọi estimated/reserved là hóa đơn hoặc coi lỗi HTTP400 miễn phí. Giá tham chiếu đã kiểm lại từ Google: 0.30/2.50 USD mỗi triệu input/output (gồm thought), https://ai.google.dev/gemini-api/docs/pricing.

Quota PostgreSQL grant `4dd2754f-e80e-4aa5-a308-7e0a593ac313`: Codex cap95, budget bổ sung1.50 USD (tính tổng reserve, không mở thêm quota theo estimate). Trần quyền còn 45 lượt Codex/50 lượt tổng; giữ ít nhất 5 cho chủ dự án, **hiện không dispatch được vì USAGE_UNKNOWN**. Đã kiểm thực tế reserve tiếp bị chặn trước insert/network; không bỏ chặn, xóa/sửa usage hoặc retry.

Cấu hình local được lưu giá trị trước thay đổi trong artifact quota: CLOUD_MAX_REQUESTS 20→113; GEMINI_MAX_REQUESTS chưa có→108; KNOWLEDGE_MAX_REQUESTS chưa có→5; CLOUD_GRANT_ID trỏ grant trên. CLOUD_BUDGET_USD=20 và mọi keys/flags giữ nguyên; giá trị20 không thay grant1.50. Default .env.example cloudOFF/max0/budget0, provider cap10, grant trống. DB advisory lock kiểm cap/budget trước reserve; test 8 luồng tranh 2 chỗ chỉ cấp2. Grant admin cấp, app chỉ SELECT và reader không được đọc grant. Lỗi/unknown usage dừng live; không tự tăng quyền để đạt 90 ca.

### F. Browser và hướng dẫn kiểm thử thủ công

18/20 luồng IAB PASS: logout, session restore, workspace, CSV, XLSX, sheet selection, consent, AI review, quota/local fallback, metadata edit, confirm/publish, ready selection, new chat, send, result table, source, history, reload/restart. Fresh Google login và hai phiên Google độc lập còn BLOCKED; lịch sử login live có manual+DB proof riêng. Sau logout, console IAB ghi `[GSI_LOGGER]: The given origin is not allowed for the given client ID.`; không có uncaught TypeError/ReferenceError được ghi nhận. Chưa đối chiếu được request origin thực tế với Google Console; không tự kết luận Client ID sai hoặc nới bảo vệ origin/backend. Cần chủ dự án đối chiếu Authorized JavaScript Origins với URL chính thức http://localhost:18181, không tạo OAuth client mới. Theo computer-use skill/guidance, không tự thao tác authentication dialog hoặc inject token để giả login. API owner A/B và auth security vẫn PASS, không đổi thành browser PASS.

Đã quan sát layout và DOM không overflow ở widths390/768/1280/1440; sidebar mobile mở/đóng, Data Manager trong viewport tablet, Escape/focus/history search hoạt động. Không gọi đó là accessibility audit đầy đủ. Busy controls disable trong request; backend idempotency kiểm riêng, chưa có stress double-click browser. Screenshot chỉ local ignored vì có tên tài khoản; không public lên GitHub.

Chủ dự án có thể đăng nhập lại `http://localhost:18181`, chọn workspace “Nghiệm thu giao diện 30-10”: hotel-ui.csv ready (4rows, quyền query chỉ Gemini), workbook-ui.xlsx ready (Data3rows, private chưa cấp cloud), fallback-ui.csv needs_review. Mở history “Tổng tiền phòng?” để xem 300.15/source mà không gọi model. Kiểm hai tài khoản, upload/local review/keyboard có thể tiếp tục độc lập. **Chưa gửi thêm câu hỏi/AI setup để nghiệm thu live cho đến khi usage/billing của lượt lỗi được xác định và quyền tiếp tục được làm rõ.** Không cần đổi keys/OAuth client.

### G. Docker, GitHub và bằng chứng

Một project chatsar, ba services healthy, volumes chatsar_database/chatsar_uploads giữ nguyên. Migration provider_grants additive, không DROP/rewrite dữ liệu cũ; rollback giữ columns/table grant, không hạ migration. Toàn app runtime hash khớp bản đã xác minh; frontend có regression thống kê. Dữ liệu Google thật2users giữ nguyên; workspace thật tăng1→2 do tạo workspace nghiệm thu synthetic có chủ đích, testusers0 sau cleanup. Có 3 file synthetic trong workspace nghiệm thu; không xóa dữ liệu Google owner qua harness. ShopQuery AI/shared Langfuse không bị restart/sửa, không prune hoặc xóa volumes/images; giữ các image rollback.

Các commit của đợt: 649dbda (Setup/quota), 92580c7 (catalog/query grounding + harness), 6fd6534 (thử Predicate và UI), sau đó commit bỏ thí nghiệm HTTP400 và ghi báo cáo này. CI của hai mốc đầu PASS; CI exact SHA cuối và local/remote được cập nhật sau push. Giữ feature/sql-foundation, PR#1 Draft, main vẫn c05f26b1a301e91e8ea6ddaadedb0e1ed03b735d.

Artifacts local: acceptance-stabilization.json (smoke), stabilization-results.json (90 case statuses/metrics/ledger), stabilization-browser.json (20 scenarios), stabilization-langfuse.json, predicate-schema-diagnostic.json, stabilization-app-fingerprints.json, stabilization-quota.json, browser-hotel-result.jpg/browser-logout.jpg. Bằng chứng cũ không ghi đè. Bộ model_live ghi app hashes/dirty-state cho lượt sau bổ sung; các lượt trước ghi rõ runtime tương ứng và so bytes cuối. Không công khai raw private content/keys/tokens.

### H. Điều kiện còn thiếu

Không chốt Phase1 đã hoàn thành. Cần giải quyết unknown usage của HTTP400 trước mọi live dispatch, xử lý các lỗi planning/output còn lại bằng thiết kế có căn cứ và regression đa domain, rồi đo lại tập hợp lệ/held-out còn thiếu trong quyền còn lại; không chỉ tăng prompt hoặc timeout. Fresh Google login có lỗi origin từ Google cần đối chiếu cấu hình; hai tài khoản cần thao tác người dùng. Các gate này ngăn READY_FOR_USER_ACCEPTANCE dù hạ tầng và deterministic tests đã PASS.

## Đợt ổn định mới — đang thực hiện, 30/10/2026

Quyền mới: thêm tối đa 100 HTTP Gemini / dự phòng 1.50 USD, Codex dùng tối đa 95, giữ ít nhất 5 thủ công; Knowledge/LlamaParse/BGE mới = 0. Quyền này thay điều kiện không dùng hai lượt còn lại của lần cấp trước, không cộng hai lượt đó vào 100. Baseline lúc 02:17:55 UTC: tổng 13, Gemini 8/Knowledge 5, hai Google users và một workspace thật. HEAD/local/remote db38d1b92f3004c518d6f5736e989ba476cac9da, working tree sạch, PR #1 Draft/CLEAN, hai CI cuối SUCCESS.

Chạy lại baseline đúng HEAD: 94 backend unit, 24 integration (7 auth +17 datasets), 25 oracle, 75 semantic gold checks, 14 manifest/DB/acceptance guard, 7 frontend SSR/DTO, types/lint/build và HTTP restart/persistence đều PASS. Chưa generation mới. Không lấy baseline làm nghiệm thu AI Setup hoặc 90 câu model-live. Root cause chi tiết lượt hotel cũ vẫn UNKNOWN; lỗi validator khóa ghép và contract dư trường được xác minh riêng, không gán cho phản hồi đã mất.

Mốc offline sửa Setup/quota: 105 unit (+11: metadata-only, khóa ghép, toàn bảng rỗng/mixed/Decimal, ID lạ/lặp/thứ tự, đơn vị cần review, structured rule), 24 integration, 16 evaluation tests (+2 quota thật: 8 threads tranh 2 reservations chỉ 2 được cấp; chặn budget, provider khác, dispatch thứ hai và unknown usage), 7 frontend SSR/DTO PASS. Lint/format/mypy/build PASS. Migration provider_grants additive đã áp dụng; reader không có quyền grant. Chưa generation mới. Đơn vị/ngày mơ hồ không còn mặc định loại toàn proposal, nhưng vẫn cần owner confirm; thay đổi dữ liệu nguy hiểm tiếp tục bị validate_rows chặn. Cấu trúc AI không cho sửa nullable/NULL sentinel/name/order/raw values. Hai plan/fixtures/gold/checksums gốc không đổi.

Smoke đầu trên app 649dbda PASS 3/3: hotel AI Setup mode=ai_proposal (đơn vị nights cần owner review), SUM room_charge 300.15, SUM labor_hours 2.50; toàn bảng/source/checksum/setup response/history sau restart PASS. HTTP SQL lần lượt 1876.99/1776.62 ms. Usage 3 dispatch/3 success, input 3477/output1190, estimated 0.0040181 USD, reserved 0.0384645 USD. Artifact acceptance-stabilization.json riêng, không ghi đè bằng chứng FAIL cũ. Query contract đã được cải thiện tiếp nên hai SQL smoke sẽ cần xác nhận cấu hình cuối; Setup contract không đổi.

Development phát hiện: (1) bộ chấm chưa nhận equivalence COUNT(DISTINCT col) với IS_NOT_NULL cùng col; PostgreSQL độc lập chứng minh tương đương scalar aggregates, sửa riêng scorer/replay không cloud, giữ gold; (2) model tự GROUP BY/projection cho scalar filtered SUM — đã làm rõ hướng dẫn chung và live cross-domain PASS; (3) model dùng tên cột room_type thay ID trong group/select/order — backend chặn đúng, schema provider nay enum IDs và ca hotel group live PASS; (4) model chép thiếu từ hỏi vào raw_user_spans gây false refusal dù phép COUNT_DISTINCT đúng — schema nay enum nguyên văn câu hỏi, guard không bỏ. Ca hỏi phí theo ID trả đúng phí nhưng thiếu cột mã theo gold còn là FAIL output contract, không gọi đó là sai số phí. Từng artifact giữ nguyên raw response/status tại thời điểm đo, không sửa expected hoặc giả PASS.

Browser IAB hiện đã có phiên Google hợp lệ, không còn blocker toàn bộ UI. Đã thực hiện trên workspace riêng “Nghiệm thu giao diện 30-10”: CSV hotel → local review → consent metadata → Gemini proposal hợp lệ → chỉnh metadata → cấp riêng quyền query Gemini → publish → chat 300.15 → source/checksum → restart → đọc lại history. XLSX Guide/Data chọn đúng sheet, mã zero đầu/NULL/Decimal giữ nguyên, publish local; hỏi nguồn private chưa cấp quyền bị DATA_PERMISSION_REQUIRED trước reserve. UI warning mất empty_count sau merge proposal được tái hiện và sửa bằng mergeProposalColumn; regression mới đưa frontend lên 8 tests PASS. Kiểm DOM widths 390/768/1280/1440 không overflow toàn trang, sidebar mobile mở/đóng, native dialog Escape và history search hoạt động. Quota Knowledge=5/đã dùng5: UI setup fallback local CALL_LIMIT_REACHED, không có HTTP Knowledge mới và không tự publish. Hai Google users thật giữ nguyên, workspace nghiệm thu dùng riêng cho synthetic, không dùng PII làm benchmark.

Nhóm paraphrase dừng khi model trả AND không children: backend chặn trước SQL. Đã siết schema provider thành các nhánh Predicate đúng grammar compiler, không thêm validator hoặc điền điều kiện. Chưa live schema nhánh tại thời điểm ghi mốc này. Một ca held-out maintenance MIN bị từ chối do result_mode top thiếu order: giữ FAIL và không dùng sửa prompt; unit/integration compiler MIN vẫn PASS. Negative đổi đơn vị trả unsupported thay clarify theo gold: giữ FAIL status, không execute. Không công bố >=95% hoặc đủ 90 ca.

## Trạng thái bản cải tiến ngày 30/10/2026

**PARTIALLY_READY — chưa nghiệm thu cuối.** Hoàn thiện độc lập Workstreams A–F: catalog nghiệp vụ, grounded values/mappings, kết quả partial, Smart Setup có consent/full-table validation/local fallback, UI sáng xanh dương và Gemini mặc định/Knowledge fallback có điều kiện. Mô hình, parser, SQLAlchemy Core, Google/session/ownership và một Compose chatsar được giữ. Không thay Master/Implementation Plan, không merge main/sang Giai đoạn 2.

| Kiểm thử bản hiện tại | Tổng | PASS | FAIL | BLOCKED | NOT_RUN |
|---|---:|---:|---:|---:|---:|
| Backend unit | 94 | 94 | 0 | 0 | 0 |
| PostgreSQL/API integration (provider mock) | 24 | 24 | 0 | 0 | 0 |
| SQL oracle baseline bất biến | 25 | 25 | 0 | 0 | 0 |
| Gold SQL cho semantic scenarios (có tham chiếu lại baseline) | 75 | 75 | 0 | 0 | 0 |
| Manifest/Decimal/DB privileges + acceptance stop guard | 14 | 14 | 0 | 0 | 0 |
| Semantic model benchmark mới | 90 | 0 | 0 | 0 | 90 |
| Provider contract, nhóm con của unit | 24 | 24 | 0 | 0 | 0 |
| Model-live mới, kế hoạch tối đa 3 lượt Gemini | 3 | 0 | 1 | 0 | 2 |
| Frontend SSR/DTO | 7 | 7 | 0 | 0 | 0 |
| Browser E2E sau redesign | 20 | 0 | 0 | 20 | 0 |
| Auth + reader security, nhóm con đã đếm ở trên | 24 | 24 | 0 | 0 | 0 |
| Docker/HTTP restart persistence | 1 luồng | 1 | 0 | 0 | 0 |

Lệnh đã chạy: backend ruff/format/mypy/pytest; `evaluations.integration`, `oracle`, `semantic`, `acceptance` prepare-only và một lượt live theo quyền bổ sung, `planning`, `persistence`, `runtime`; `CHATSAR_POSTGRES_TESTS=1 unittest discover -s evaluations/tests`; frontend typecheck/test/build. Một cảnh báo deprecation từ Starlette/httpx, không skip test. Các hàng nhóm con không cộng thành tổng độc lập. Lượt live mới chỉ tới AI Setup, chưa tới SQL: chưa có mẫu số release accuracy/semantic coverage/false refusal/silent wrong answer hoặc p50/p95 SQL model latency mới. Không lấy 75 gold checks hoặc 94 unit làm bằng chứng hiểu câu hỏi 95%.

Semantic scenarios đã khóa checksum riêng: basic 30, paraphrase 20, edge 15, negative 10, follow-up 10, metamorphic 5; sáu domain logistics/hotel/energy/agriculture/library/maintenance. Maintenance là schema mới, 5 ca held-out chưa dùng tuning/model-live; labels do người viết fixture biết, không phải blind external benchmark. Gold SQL/expected gốc giữ nguyên; 75 gold checks không phải 75 câu model trả đúng. 15 tình huống không phải SQL dùng context/negative expectations. `semantic.json` có metric/filter/group/order/limit gold riêng; expected không đi vào prompt.

So cấu trúc offline: schema nội bộ 17 properties/3804 bytes, schema provider 12 properties/3260 bytes; Gemini không còn nhận bản schema lặp trong prompt. Tám fixture cấu trúc cho A một lượt và B tách/ghép hai bước đều nhận 1 hợp lệ, chặn 7 không hợp lệ; đây là kiểm consistency, không phải thí nghiệm hai model calls hoặc so semantic accuracy. Chưa có bằng chứng chất lượng tốt hơn để biện minh chi phí/latency hai lượt, nên giữ A. Token/cost/model latency so trước–sau: NOT_RUN. Deadline 60 s giữ nguyên; fallback chỉ bắt đầu trong 20 s đầu để còn khoảng chờ provider/SQL dưới client/proxy 90 s.

Vòng kiểm oracle phát hiện guard “giá trị không tồn tại thì luôn clarify” quá chặt với tập rỗng hợp lệ. Đã sửa tại executor/evidence: literal nguyên văn giữ nguyên điều kiện, source_match=no_match và cảnh báo; SQL SUM(empty) vẫn NULL. Mapping sai/xung đột exact value bị chặn khi confirm. Có HTTP regression kiểm NULL/cảnh báo và không tạo 0. Mapping ngày theo format owner đã xác nhận được đổi sang ISO có kiểm chứng; date_format/decimal_separator được đưa vào catalog cho provider.

Prepare-only qua proxy web/PostgreSQL thật đã đối chiếu tất cả typed rows/NULL/TEXT zero đầu của hotel và maintenance; checksums CSV lần lượt `ea5702c6d69013434b897044b1a6f320de770876b214a71df25839b5d28e1311`, `1d3bcbb55df03218b8bc3549179f144d87a0a52fabc45e49b9b4ed0cc186d5b8`. Không gọi generation; dọn đúng test owner sau phép thử. Google users thật 2, workspace thật 1 vẫn còn, test users 0 sau cleanup. Migrations: foundation/identity/datasets/conversation/catalog. Langfuse Observations v2 HTTP 200, đọc lại trace metadata mới (ví dụ `fce78f8ba9cf853b2d3f6b13b58cba6d`); đó là trace từ HTTP tests, không phải provider model-live mới.

Chủ dự án đã cấp tối đa **3 HTTP requests Gemini, trần 0.06 USD** ngày 30/10/2026 cho AI Setup hotel → hotel SUM 300.15 → maintenance SUM 2.50, với điều kiện dừng khi provider hoặc kết quả lỗi. Precheck ledger 12 (Gemini 7/Knowledge 5), flags/model hợp lệ, reserve tối đa ba lượt 0.05952 USD; không sửa .env.

### Kết quả một lượt live được cấp bổ sung

Chạy trên commit `d36c8447dac77a88c5a1e694056ccf77de6a304e`. Gemini trả SetupProposal hợp lệ về JSON/Pydantic sau **4993.72 ms**, nhưng backend trả `mode=local`, `SETUP_PROPOSAL_REJECTED`; AI Setup **FAIL nghiệm thu**. Đây là lỗi ở bước kiểm tra đề xuất, không phải timeout hoặc lỗi truy cập provider. Chưa đủ bằng chứng kết luận đề xuất model sai hay validator từ chối sai. Không publish đề xuất AI bị từ chối; fallback local vẫn trả về an toàn. Harness đã dừng ngay, hai câu SQL còn lại **NOT_RUN**, không retry hoặc gọi Knowledge.

Usage lượt này: input **790**, output **900**, thought **0**; chi phí ước tính **0.002487 USD**, reserve **0.0122368 USD**, không phải hóa đơn. Usage record `ba4e43f0-cf83-4238-85f8-0584d3dfeb8c`, source checksum `ea5702c6d69013434b897044b1a6f320de770876b214a71df25839b5d28e1311`; Langfuse Observations v2 HTTP 200, provider trace `3f7c5b09e53bb690738330c9dd5103a0`. Ledger hiện **13 reservations: Gemini 8, Knowledge 5**. Hai lượt được cấp chưa dùng; điều kiện dừng đã có hiệu lực nên Codex không tự sử dụng tiếp.

Giới hạn bằng chứng: response `validation_errors=[]` mô tả proposal local sau fallback, trong khi lý do loại AI nằm trong `proposal.notes`. Harness cũ chưa lưu notes trước cleanup test owner, nên lý do cụ thể đã mất; **root cause chi tiết UNKNOWN**, không đoán lỗi schema/type/key/date hoặc sửa prompt/validator theo phỏng đoán. Đã sửa riêng harness lưu `rejection_notes` và exit code 1 khi live FAIL. Regression offline xác nhận notes được lưu trước cleanup, chỉ một setup request và không gửi SQL tiếp; không có generation bổ sung. Dữ liệu Google users thật 2/workspace 1 giữ nguyên, test users 0. Bằng chứng local: `artifacts/acceptance.json`, `artifacts/acceptance-langfuse.json`.

Gate AI Setup còn FAIL; hai SQL và độ chính xác benchmark chưa nghiệm thu, không tuyên bố khắc phục hotel timeout hoặc đạt >=95% semantic accuracy. Knowledge 403 ở lần live gần nhất và browser E2E vẫn là các giới hạn độc lập. Không merge hoặc chuyển Giai đoạn 2.

Browser IAB đọc được trang login mới và nút Google; khi chọn phiên Cốc Cốc, tool dừng vì browser URL policy enforcement chưa hỗ trợ. Đã dừng UI automation, không dùng công cụ khác vượt chặn. Google live trước redesign có xác nhận thủ công + DB; 20 luồng E2E và kiểm tra visual responsive của UI mới chưa được nghiệm thu. Chủ dự án giữ quyền user acceptance.

### Chủ dự án tự kiểm thử

1. Mở `http://localhost:18181`, đăng nhập Google; tạo/chọn không gian ở sidebar.
2. Mở Quản lý dữ liệu, tải CSV/XLSX; chọn sheet nếu workbook có nhiều sheet.
3. Chọn Phân tích local, hoặc đồng ý metadata rồi Nhận đề xuất AI khi có quyền/hạn mức. Lỗi AI vẫn dùng được local review.
4. Xem cột/ô trống; chỉnh đơn vị, mô tả hoặc ngày ở Chỉnh sửa chi tiết nếu cần. Đề xuất đã lưu có thể mở lại mà không gọi AI.
5. Nếu hỏi nguồn private, cấp quyền metadata/giá trị giới hạn/câu hỏi cho đúng provider; không đổi dữ liệu thật thành synthetic.
6. Xác nhận và sử dụng dữ liệu, đóng hộp thoại, chọn nguồn ở header rồi hỏi. Xem bảng, Nguồn và cách tính; nếu partial thì chưa phải danh sách đầy đủ.
7. Đọc lịch sử, refresh, logout/login lại; thử tài khoản khác để kiểm isolation. Nếu timeout, cập nhật lịch sử trước khi gửi lại, không bấm lặp. Phê duyệt merge/User Acceptance là quyết định riêng của chủ dự án.

## Lịch sử triển khai trước bản cải tiến

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

F2 foundation: users/sessions/workspaces, Google ID-token + nonce/CSRF, expiry/revoke/rotation và owner guards; 17 unit + 7 API integration PASS tại `8dbdee9f2aa1326d85c245859dc5213e82398841`, CI https://github.com/MinhHoang1403/ChatSAR/actions/runs/40852418438 . Ban đầu Google live BLOCKED, F3/F4 được chủ dự án cho phép tiếp tục qua harness. Sau khi chủ dự án bổ sung Client ID và kiểm thử browser, đã sửa canonical origin/clock skew. **Google login/logout/relogin + workspace live hiện PASS thủ công và có dữ liệu DB thật:** 2 Google users, 1 active session, 2 revoked sessions, 1 workspace tại lần đối chiếu; không ghi sub/email/token. Session/workspace persistence vẫn được kiểm bằng HTTP/restart harness. Không có runtime endpoint đăng nhập test.

F3: upload CSV/XLSX local, preview/chọn sheet, review types/NULL/khóa/đơn vị/timezone/grain và publish atomic thành bảng `data.r_<revision UUID>`. Original file trong volume `chatsar_uploads`; checksum và catalog ở PostgreSQL. Nguồn private mặc định; chỉ khi user xác nhận synthetic mới đủ điều kiện gửi metadata cho smoke test AI. Quan hệ hiện chưa cấu hình; không suy JOIN.

Kiểm tra F3 local: 23 unit tests tổng cộng, 13 integration tests (7 auth + 6 ingestion) PASS. Harness HTTP thật chạy upload → preview → confirm → ready; sau restart session/workspace/file/checksum/catalog/typed rows giữ nguyên, gồm Decimal 0.10/0.20, TEXT 0007 và NULL. Duplicate key/invalid date không publish; source corrupt/cap bị từ chối; upload cùng file trả revision cũ; interrupted job chuyển failed rồi retry cùng revision. CI PASS tại `a0abd0e9b40bd3676a6e4917c82108d239fa503b`: https://github.com/MinhHoang1403/ChatSAR/actions/runs/40854606057 . Browser automation/Google live vẫn chưa được thực hiện, không lấy tests API làm browser PASS.

## F4 — phần triển khai và kiểm thử

Một đường Question → proposal → catalog/literal binding → SQLAlchemy Core SELECT → reader PostgreSQL → typed envelope. Không nhận SQL/role/schema/owner từ model hoặc client. Có conversations/messages/result references, idempotency, follow-up từ question + plan của lượt answered cùng revision; đổi nguồn trả STALE_CONTEXT. React có chọn nguồn/provider, chat, loading/errors, bảng kết quả, nguồn/cách tính và lịch sử. UI đã build và phục vụ qua Docker; chưa coi authenticated UI/browser E2E là PASS.

| Kiểm tra cuối phần độc lập | Kết quả | Bằng chứng |
|---|---|---|
| Backend unit | PASS 65 tests | `uv run --frozen pytest -q` trong backend; gồm canonical origin, token RSA ký thật/clock window, hạn mức tổng/provider độc lập, transport SDK và tracing failure isolation |
| Lint/format/mypy | PASS | `ruff check app tests`, `ruff format --check app tests`, `mypy` strict, 14 app modules |
| PostgreSQL/API integration | PASS 18 tests | `python -m evaluations.integration`: 7 auth + 11 ingestion/query/chat; provider chỉ mock trong harness |
| Independent oracle | PASS 25 cases | `python -m evaluations.oracle`; gold SQL không import compiler; manifest/checksums gốc không đổi |
| Manifest/Decimal/DB privileges | PASS 10 tests, không skip | `CHATSAR_POSTGRES_TESTS=1 python -m unittest discover -s evaluations/tests -v` |
| Fixture fidelity | PASS 3 domains | `python -m evaluations.model_live --providers gemini --cases logistics_sum hotel_sum library_sum --prepare-only`; tất cả rows/columns/NULL đối chiếu lại sau ingestion, không gọi model |
| Frontend TypeScript/build | PASS | `npm run typecheck`, `npm run build`; không phải browser E2E |
| HTTP/Docker persistence | PASS | `python -m evaluations.persistence`; session/workspace/source/catalog/typed rows và lịch sử refusal còn sau restart; không gọi model |
| Lịch sử answer model thật | PASS trên 2 ca đã trả đúng | `evaluations.model_live --restart` so sánh nguyên envelope/result refs/revision trước/sau restart, không gọi lại model |
| Langfuse thật | PASS | Auth HTTP 200, Observations v2 HTTP 200, đọc lại các bước provider/binding/execution/answer cùng trace |
| Google live + workspace browser | PASS thủ công + DB | Người dùng xác nhận, DB có users/session revoke/workspace thật sau sửa; không phải automated browser E2E |
| Chat/result browser E2E | BLOCKED | Kiểm tra lại công cụ trả `The browser access host is unavailable`; người dùng yêu cầu tự test và sẽ test browser sau; HTTP không thay thế browser PASS |
| CI F4 core | PASS | `1a5692d69c797695c99f6d8e8d452e3656c5009e`, https://github.com/MinhHoang1403/ChatSAR/actions/runs/40900427055 ; phần sửa auth sau đó phải chạy CI riêng |
| CI auth + quota | PASS | `d94670e13a3fae94af25bf4f9e29d59a3a411555`: https://github.com/MinhHoang1403/ChatSAR/actions/runs/40902931948 ; `8f1d8951907364102036c61d6a02ecf0b386ae45`: https://github.com/MinhHoang1403/ChatSAR/actions/runs/40903381443 |

Integration đã kiểm COUNT rows/non-null/distinct, SUM/AVG/MIN/MAX, NULL aggregate, Decimal, group/order/limit, AND/OR/IN, timestamp `[start,end)` theo timezone, literal chính xác, owner A/B, result ownership, idempotency/conflict, source chưa ready, stale context và raw SQL field bị chặn. Metamorphic test đảo thứ tự/thêm dòng ngoài filter giữ nguyên SUM. Chưa có JOIN, suy quan hệ, tự quy đổi đơn vị hoặc tự suy ngày đầu/cuối tháng từ ngôn ngữ.

Coverage guard đối chiếu các span và entity đã biết; không chứng minh mọi qualifier trong ngôn ngữ đều được model hiểu đúng. Tám negative cases trong manifest là baseline: các guard liên quan có unit/integration tests, nhưng **chưa chạy toàn bộ 8 câu tự nhiên qua model thật**. Không ghi đây là semantic negative 8/8 PASS.

## Model-live — số đo và giới hạn

Cấu hình do chủ dự án cập nhật: cloud allowed, max 10 requests tổng, budget 10 USD; Gemini/Knowledge/Langfuse enabled tại lần chạy cuối. Không sửa `.env`, không dùng LlamaParse hay GPU BGE. Chủ dự án đã bổ sung Google Client ID; public config HTTP 200 xác nhận sự hiện diện và định dạng mà không in giá trị. Dependency thực: google-genai 2.34.0, langfuse 5.0.4; server Langfuse 4.70.1.

Tại mốc trước quyền bổ sung, ledger có **10 reservations: Gemini 5, Knowledge 5**. Hai thử Gemini khi flag còn false bị chặn trước reserve/network, không tính là direct calls. Trình tự thử và failures được giữ trong `artifacts/model-live.json` local, không xóa/reset ledger. Sau hai lượt bổ sung dưới đây, tổng là **12: Gemini 7, Knowledge 5**.

Guard kiểm tổng reservations theo CLOUD_MAX_REQUESTS và từng provider theo cap 10 một cách độc lập; không chèn cap tổng 10 cứng khác cấu hình. Thay đổi này không tự cấp quyền chi tiêu: tại mốc đó `.env` max 10 và bộ đếm đã hết; mọi lượt bổ sung cần chủ dự án cấp rõ ràng. Tests với max 12 dùng DB giả lập để chứng minh không lẫn hai loại hạn mức.

**Quyền bổ sung sau báo cáo trên:** chủ dự án đã đồng ý cấp đúng 2 HTTP requests Gemini để nghiệm thu browser trên `logistics-browser.csv` và `hotel-browser.csv`, dự phòng dưới 0.04 USD. Người dùng tự đặt `.env` max requests 20/budget 20 USD; Codex giữ file đó và chỉ sử dụng hai lượt bổ sung được duyệt, không suy ra được quyền dùng hết 20. API đã nạp lại cấu hình; baseline ledger trước QA là 10 (Gemini 5, Knowledge 5). Kết quả browser phải đối chiếu DB/oracle trước khi cập nhật PASS, không chỉ dựa vào việc đã cấp hạn mức.

### Hai lượt tự kiểm thử bổ sung — HTTP, không phải browser

Người dùng yêu cầu Codex tự test và sẽ kiểm browser sau. Inventory công cụ trả browsers rỗng cùng lỗi `The browser access host is unavailable`; không dùng automation khác để vượt giới hạn URL policy của Cốc Cốc. Thực hiện qua proxy web chính thức và TestSession được kiểm soát, không impersonate Google user thật hoặc thêm endpoint test login. Hai lượt chạy trên phần app của commit `8f1d8951907364102036c61d6a02ecf0b386ae45` với timeout 30 giây; thay đổi deadline/tracing sau QA chỉ được kiểm thử offline trong vòng này.

| CSV/câu hỏi | Kết quả thực tế | Bằng chứng |
|---|---|---|
| logistics-browser.csv — Tổng phí tại quận 3? | PASS `10.00`, numeric string; filter giữ nguyên `quận 3`; nguồn/rows/review khớp trước gọi model | revision `f12cec8a-fa7c-4c44-a650-b7ace245659f`, result `011a999c-784e-4430-bd7a-ddfd52f77203`, request `ec0480a6-5e25-41bc-bb7f-c1abacc68fd4`, trace `d084a77017adb6ae38aeb2577e2ea17f` |
| hotel-browser.csv — Tổng tiền phòng? | FAIL ở provider: `PROVIDER_TIMEOUT` / APITimeoutError sau khoảng 30.25 s; không execute SQL, không tạo fact giả hoặc đổi timeout thành 0 | revision `95ce52d3-cdbb-4df0-ad13-6ee945e5cd14`, request `bae51264-b9be-481c-8809-54f454217c18`, trace `6a3cd664db8df92a9ba093875b9c300b` |

Logistics: input/output 1911/444; provider latency 29.16 s, HTTP toàn luồng 29.49 s, SQL 22.36 ms. Hai checksums lần lượt `1571567605a122bd1e7eeb9883a2ee0e0f2563143a5326a2311f2590ef6aa006`, `60be8100bdc9e4285162366d0b4b5c5cafcc2e350d1cbaafd335184b7e163be5`. Expected Decimal độc lập là 10.00 và 300.15; không sửa expected theo response. GET result/history khớp envelope; sau restart nguyên stack, typed rows/source/checksum/history của cả hai lượt vẫn giữ nguyên, không gọi lại model. Harness đã dọn đúng test owner UUID và bảng/file của nó; dữ liệu Google user thật được giữ nguyên. Bằng chứng local đã lọc ở `artifacts/browser-qa.json`.

Đã dùng đúng 2 reservations bổ sung, không gọi lại sau lỗi. Langfuse v2 trả HTTP 200 cho cả hai traces; ca logistics có provider → validation passed → execution → answered, ca hotel có APITimeoutError và answer provider_unavailable. Tổng hai vòng Gemini: 3/7 application attempts trả đúng, gồm logistics 2/4, hotel 0/2, library 1/1; cả 3 queries đã execute đều đúng gold. Đây là lịch sử có thay đổi contract/timeout giữa các vòng, không phải accuracy của một benchmark cố định hoặc 3 câu hỏi khác nhau. Knowledge vẫn 0 answered/5 attempts ở lần kiểm tra cuối; không retry Knowledge.

Sau số đo sát trần 30 s, provider deadline đã đổi thành 60 s, nginx proxy_read_timeout và HTTP harness thành 90 s. Sửa này PASS offline/unit/integration/build; **chưa được xác nhận model-live khắc phục timeout**, vì hai lượt bổ sung đã dùng hết. Tracing error giữ mã AppError an toàn thay vì chỉ ghi tên exception; test bảo đảm lỗi tracing không thay kết quả nghiệp vụ hoặc ghi message riêng tư. Không sửa prompt, model, dữ liệu hoặc gold để che lỗi.

Tổng chi phí ước tính từ mọi usage Gemini đã biết sau bổ sung khoảng **0.0055238 USD**; tổng reserve Gemini **0.0971122 USD**. Phần tăng có usage là 0.0016833 USD; lượt timeout không có usage nên chi phí thực chưa biết. Đây không phải hóa đơn và không coi thiếu usage là miễn phí. Agent dừng ở tổng 12 reservations dù cấu hình local là 20.

| Ca model trả đúng | Oracle / actual | Revision nguồn / request |
|---|---|---|
| Gemini logistics_exact_district (regression) | `10.00` / `10.00`, filter TEXT giữ `quận 3`, SUM fee | revision `901d90f1-bca8-4b90-b074-b0a0835760eb`; request `63125e4b-6cf0-4381-b758-17d83be39640` |
| Gemini library_sum (held-out, chạy một lần) | `1.25` / `1.25`, SUM fine | revision `9a8a0f9e-8948-4cdb-87ca-4f2277674f36`; request `fe0de9ed-efa8-468c-a805-966b15835ee6` |

Checksum CSV của hai ca lần lượt `0444352adc8414e91ead9823aa9c0de9b581833123447da0f2afd91faadcd54b`, `e73476d4e27fa127279d6314ef3bebf47e5950c63041d15a82fbdd45ffac5d57`. Sources/users của harness được dọn đúng UUID sau đối chiếu; kết quả/số đo synthetic được lưu trong artifact local và báo cáo này, không phải dữ liệu demo còn sẵn trong tài khoản người dùng.

Gemini: 2/5 application attempts trả answer đúng; hai failure về schema trước khi hoàn thiện contract, một APITimeoutError ở ca hotel_sum (20 giây). Hai queries đã compile/execute đều chạy thành công và đúng gold (2/2 executed), gồm một ca critical `quận 3` và một ca held-out. Không dùng tỷ lệ 2/2 này làm accuracy toàn benchmark. Latency end-to-end khoảng 21.15 s và 18.62 s; SQL của ca thư viện khoảng 16.8 ms. Tokens hai ca: input/output 2035/448 và 1977/302, thought 0. Timeout hiện được chốt 30 giây, không có tự fallback.

Knowledge: 4 JSON proposals nhưng bị chặn vì thiếu/mất trường catalog/query hoặc coverage; không trả fact sai ra người dùng. Lần thứ năm HTTP 403 từ Docker, đã dừng Knowledge ngay, không prompt tuning để vượt quyền. Usage có thật ở 4 responses: 824/764, 824/738, 830/829, 1974/1030; response 403 không có usage. **Model-live chưa đạt**, hiện BLOCKED ở permission/network 403; không gửi Authorization/dummy key. So sánh chất lượng trên hai câu logistics_sum/hotel_sum đã thử nhưng chưa có tập hai provider thành công để kết luận model nào tốt hơn.

Tổng usage Gemini đã biết (kể cả một response schema lỗi có usage 1998/65) tương ứng khoảng **0.0038405 USD** theo giá công bố 0.30/2.50 USD mỗi triệu input/output tokens. Không phải hóa đơn; các request không trả usage chưa biết chi phí. Tổng các khoản reserve Gemini là **0.0693980 USD**, là dự phòng của ứng dụng, không phải mức tiền thực đã thu. Knowledge cost unknown, không ghi bằng 0.

**Giới hạn kiểm kê HTTP lịch sử:** test transport phát hiện SDK mutates attempts=0 → 1 rồi bridge Interactions hiểu là một retry cho HTTP 429/5xx. Vì vậy 10 ledger reservations không chứng minh có đúng 10 HTTP requests lịch sử. Không có audit transport đầy đủ cho các lượt trước; không bịa số request/billing. Đã dừng gọi live và bổ sung `request_client` chặn lần dispatch thứ hai trước transport. Test SDK thật qua MockTransport với 503/429/timeout và socket bị cấm xác nhận chỉ một dispatch; không phát sinh cloud. Không sửa vendor SDK hoặc coi mock này là lần nghiệm thu provider-live bổ sung. Muốn benchmark tiếp cần chủ dự án cấp giới hạn mới; không tự tăng cấu hình hay reset ledger.

**Fidelity harness:** CSV lịch sử làm NULL delivery_status thành empty TEXT do review sentinel. Hai ca model trả đúng không dùng cột đó; các cột SUM/filter liên quan giữ đúng giá trị, kết quả gold không thay đổi. Đã sửa harness dùng sentinel không trùng dữ liệu + nullable review rõ ràng, và kiểm mọi ô/NULL ở 3 domain qua HTTP; không gọi model lại hoặc giả rằng model đã được chạy trên fixture mới. Fixtures/gold gốc bất biến.

Langfuse đọc lại trace `9b9246e1a14e141f903f27ed244afe10`: provider input/output tokens + latency, bind_and_compile validation passed, execute_read_only row_count 1 + latency, answer_question answered. Metadata mặc định không gửi question/raw rows/SQL/secrets; dùng API v2 vì API traces cũ trả 404 trên server này. Bằng chứng đã lọc ở `artifacts/langfuse-proof.json` local.

## Exit gate tại mốc trước bản cải tiến

### Workstream B — 30/10/2026

74 unit + 20 integration (7 auth, 13 datasets/query) PASS; ruff/format/mypy PASS. Ca regression mới kiểm mapping có thật, từ chối mapping sai, metadata tồn tại sau publish, qualifier tìm từ DB bị bỏ sót dù model tự khai coverage, top N thiếu order/limit, metric không cộng được và LIMIT N+1. HTTP integration xác nhận safety truncation trả partial/reference_only; SQL oracle thuần giữ SUM(empty)=NULL. Migration catalog đã chạy trên project chatsar, chỉ thêm cột và bảo toàn dữ liệu cũ. Không generation call mới. Model accuracy/token/latency của schema rút gọn chưa đo live; không coi offline PASS là nghiệm thu model.

### Workstream C — backend Smart Setup

82 unit + 23 integration PASS (7 auth, 16 datasets/query/setup); ruff/format/mypy PASS. Cùng adapter/hạn mức/transport chính thức phục vụ hai contract QueryPlan và SetupProposal, không thêm SDK path. Tests local giữ TEXT zero đầu/Decimal/NULL/empty, phát hiện duplicate key/AI type sai/date mơ hồ; integration kiểm consent, owner B bị chặn trước provider, timeout fallback local, idempotency không gọi lại, đề xuất sai bị loại, đề xuất hợp lệ vẫn needs_review và restart pending chuyển interrupted. File/publish đi qua cùng validate_rows, không ghi lại dữ liệu AI. AI-live chưa chạy vì chưa cấp lượt mới; UX review thuộc Workstream D.

### Workstream D — UI

Frontend TypeScript/build + 6 SSR/DTO tests PASS. Giao diện sáng xanh dương, sidebar lịch sử/tìm kiếm/workspace/account, header nguồn, chat/composer riêng, Data Manager modal và AI review/local review/advanced metadata/sharing consent. Client có deadline 90 s và giữ idempotency để không hiểu timeout là quyền gọi lại. Browser IAB đã đọc được màn hình login mới và nút Google thật sau build; chưa đăng nhập IAB. Khi chọn phiên Cốc Cốc hiện hữu, công cụ dừng với lý do URL policy enforcement chưa hỗ trợ browser Windows này; đã dừng mọi UI automation trong lượt. Không dùng HTTP/SSR để đánh browser E2E hoặc responsive visual PASS.

### Workstream E — provider và số đo

89 unit + 24 integration (7 auth, 17 dataset/query/setup/provider) và 6 frontend SSR/DTO PASS. Mock integration: HTTP transient + opt-in chuyển đúng một lần sang Knowledge; tắt opt-in/timeout/schema failure không chuyển. Unit kiểm quyền dữ liệu, provider đang chọn và trạng thái Knowledge chưa xác nhận. Transport SDK vẫn chặn dispatch thứ hai; no vendor upgrade. Có timing catalog/provider/binding/execution/composition và tổng xử lý server; không tăng deadline. Chưa có số đo tokens/latency/cost mới của model thật, chưa so sánh quality trước/sau. Knowledge live vẫn bị 403 lần gần nhất, vì vậy fallback tự động không sẵn sàng; người dùng có thể chủ động chọn khi ở mạng được phép. Không gọi generation mới.

**Phần triển khai F1–F4 đã có; chưa nghiệm thu toàn bộ Giai đoạn 1.** Google OAuth/workspace live đã xác minh; browser E2E BLOCKED bởi tool và để người dùng test sau. Hai ca HTTP bổ sung có 1 PASS, 1 provider timeout; deadline mới chưa được nghiệm thu live. Knowledge bị 403 ở lần thử cuối. Chưa chạy toàn bộ development/regression/held-out/negative model benchmark; ba ca library held-out còn NOT_RUN, không tuning theo ca library_sum đã đo. Chưa có phép đo release accuracy/latency đầy đủ hoặc xác nhận số HTTP requests lịch sử trước SDK guard. Đã dùng đủ 12 reservations trong quyền hiện tại, không tự gọi thêm. Giữ feature branch/PR nháp; không merge main, không sang Giai đoạn 2.

## Google OAuth khi frontend/backend đã xác minh

Frontend chính thức local: `http://localhost:18181`; backend trực tiếp: `http://127.0.0.1:18081`. Browser gọi API qua proxy cùng origin `http://localhost:18181/api`, nên không cần CORS đa origin. Google Identity Services dùng JS callback nhận ID token và POST cùng origin tới `/api/auth/google`, có CSRF cookie/token và nonce. Với chế độ popup callback này không dùng OAuth authorization-code redirect URI. Authorized JavaScript Origin cần khai báo đúng `http://localhost:18181`; không thêm đường dẫn `/api`. Không tạo/sửa OAuth client của ShopQuery.

Live test đã phát hiện hai lỗi: mở frontend qua 127.0.0.1 khác APP_ORIGIN và token Google bị verifier báo clock_early với skew 0. Giao diện nay chuyển về origin chuẩn trước Google Login; backend vẫn từ chối origin khác. Verifier dùng dung sai iat/exp 10 giây của google-auth, sau đó app vẫn kiểm exp còn hiệu lực, aud/iss/sub/nonce. Unit test dùng chữ ký RSA thật, chỉ mock nguồn certificate: +5 giây chấp nhận, +60 giây/expired/tampered signature/wrong nonce từ chối. Certificate request timeout 5 giây; lỗi mạng trả 503 riêng; diagnostics chỉ log reason cố định, không log token/claims. Không thay đổi đồng hồ Windows.
