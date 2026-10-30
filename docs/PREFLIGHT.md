# Bằng chứng triển khai Giai đoạn 1

## Đợt ổn định mới — đang thực hiện, 30/10/2026

Quyền mới: thêm tối đa 100 HTTP Gemini / dự phòng 1.50 USD, Codex dùng tối đa 95, giữ ít nhất 5 thủ công; Knowledge/LlamaParse/BGE mới = 0. Quyền này thay điều kiện không dùng hai lượt còn lại của lần cấp trước, không cộng hai lượt đó vào 100. Baseline lúc 02:17:55 UTC: tổng 13, Gemini 8/Knowledge 5, hai Google users và một workspace thật. HEAD/local/remote db38d1b92f3004c518d6f5736e989ba476cac9da, working tree sạch, PR #1 Draft/CLEAN, hai CI cuối SUCCESS.

Chạy lại baseline đúng HEAD: 94 backend unit, 24 integration (7 auth +17 datasets), 25 oracle, 75 semantic gold checks, 14 manifest/DB/acceptance guard, 7 frontend SSR/DTO, types/lint/build và HTTP restart/persistence đều PASS. Chưa generation mới. Không lấy baseline làm nghiệm thu AI Setup hoặc 90 câu model-live. Root cause chi tiết lượt hotel cũ vẫn UNKNOWN; lỗi validator khóa ghép và contract dư trường được xác minh riêng, không gán cho phản hồi đã mất.

Mốc offline sửa Setup/quota: 105 unit (+11: metadata-only, khóa ghép, toàn bảng rỗng/mixed/Decimal, ID lạ/lặp/thứ tự, đơn vị cần review, structured rule), 24 integration, 16 evaluation tests (+2 quota thật: 8 threads tranh 2 reservations chỉ 2 được cấp; chặn budget, provider khác, dispatch thứ hai và unknown usage), 7 frontend SSR/DTO PASS. Lint/format/mypy/build PASS. Migration provider_grants additive đã áp dụng; reader không có quyền grant. Chưa generation mới. Đơn vị/ngày mơ hồ không còn mặc định loại toàn proposal, nhưng vẫn cần owner confirm; thay đổi dữ liệu nguy hiểm tiếp tục bị validate_rows chặn. Cấu trúc AI không cho sửa nullable/NULL sentinel/name/order/raw values. Hai plan/fixtures/gold/checksums gốc không đổi.

Smoke đầu trên app 649dbda PASS 3/3: hotel AI Setup mode=ai_proposal (đơn vị nights cần owner review), SUM room_charge 300.15, SUM labor_hours 2.50; toàn bảng/source/checksum/setup response/history sau restart PASS. HTTP SQL lần lượt 1876.99/1776.62 ms. Usage 3 dispatch/3 success, input 3477/output1190, estimated 0.0040181 USD, reserved 0.0384645 USD. Artifact acceptance-stabilization.json riêng, không ghi đè bằng chứng FAIL cũ. Query contract đã được cải thiện tiếp nên hai SQL smoke sẽ cần xác nhận cấu hình cuối; Setup contract không đổi.

Development phát hiện: (1) bộ chấm chưa nhận equivalence COUNT(DISTINCT col) với IS_NOT_NULL cùng col; PostgreSQL độc lập chứng minh tương đương scalar aggregates, sửa riêng scorer/replay không cloud, giữ gold; (2) model tự GROUP BY/projection cho scalar filtered SUM — đã làm rõ hướng dẫn chung và live cross-domain PASS; (3) model dùng tên cột room_type thay ID trong group/select/order — backend chặn đúng, schema provider nay enum IDs và ca hotel group live PASS; (4) model chép thiếu từ hỏi vào raw_user_spans gây false refusal dù phép COUNT_DISTINCT đúng — schema nay enum nguyên văn câu hỏi, guard không bỏ. Ca hỏi phí theo ID trả đúng phí nhưng thiếu cột mã theo gold còn là FAIL output contract, không gọi đó là sai số phí. Từng artifact giữ nguyên raw response/status tại thời điểm đo, không sửa expected hoặc giả PASS.

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
