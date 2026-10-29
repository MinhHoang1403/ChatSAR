# Bằng chứng triển khai Giai đoạn 1

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
| Backend unit | PASS 61 tests | `uv run --frozen pytest -q` trong backend; gồm canonical origin, token RSA ký thật/clock window và transport SDK với mạng bị cấm |
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
| Chat/result browser E2E | Chưa nghiệm thu | UI đã build; cần thao tác với nguồn synthetic và hạn mức model mới; automation Cốc Cốc vẫn bị chặn URL policy |
| CI F4 core | PASS | `1a5692d69c797695c99f6d8e8d452e3656c5009e`, https://github.com/MinhHoang1403/ChatSAR/actions/runs/40900427055 ; phần sửa auth sau đó phải chạy CI riêng |

Integration đã kiểm COUNT rows/non-null/distinct, SUM/AVG/MIN/MAX, NULL aggregate, Decimal, group/order/limit, AND/OR/IN, timestamp `[start,end)` theo timezone, literal chính xác, owner A/B, result ownership, idempotency/conflict, source chưa ready, stale context và raw SQL field bị chặn. Metamorphic test đảo thứ tự/thêm dòng ngoài filter giữ nguyên SUM. Chưa có JOIN, suy quan hệ, tự quy đổi đơn vị hoặc tự suy ngày đầu/cuối tháng từ ngôn ngữ.

Coverage guard đối chiếu các span và entity đã biết; không chứng minh mọi qualifier trong ngôn ngữ đều được model hiểu đúng. Tám negative cases trong manifest là baseline: các guard liên quan có unit/integration tests, nhưng **chưa chạy toàn bộ 8 câu tự nhiên qua model thật**. Không ghi đây là semantic negative 8/8 PASS.

## Model-live — số đo và giới hạn

Cấu hình do chủ dự án cập nhật: cloud allowed, max 10 requests tổng, budget 10 USD; Gemini/Knowledge/Langfuse enabled tại lần chạy cuối. Không sửa `.env`, không dùng LlamaParse hay GPU BGE. Chủ dự án đã bổ sung Google Client ID; public config HTTP 200 xác nhận sự hiện diện và định dạng mà không in giá trị. Dependency thực: google-genai 2.34.0, langfuse 5.0.4; server Langfuse 4.70.1.

Ledger có **10 reservations: Gemini 5, Knowledge 5**. Hai thử Gemini khi flag còn false bị chặn trước reserve/network, không tính là direct calls. Trình tự thử và failures được giữ trong `artifacts/model-live.json` local, không xóa/reset ledger.

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

## Exit gate hiện tại

**Phần triển khai F1–F4 đã có; chưa nghiệm thu toàn bộ Giai đoạn 1.** Google OAuth/workspace live đã xác minh; chat/result browser E2E chưa nghiệm thu. Knowledge-live gặp 403. Chưa chạy toàn bộ development/regression/held-out/negative model benchmark; ba ca library held-out còn NOT_RUN, không tuning theo ca library_sum đã đo. Chưa có phép đo release accuracy/latency đầy đủ hoặc xác nhận số HTTP requests lịch sử của SDK. Giữ feature branch; không merge main, không sang Giai đoạn 2.

## Google OAuth khi frontend/backend đã xác minh

Frontend chính thức local: `http://localhost:18181`; backend trực tiếp: `http://127.0.0.1:18081`. Browser gọi API qua proxy cùng origin `http://localhost:18181/api`, nên không cần CORS đa origin. Google Identity Services dùng JS callback nhận ID token và POST cùng origin tới `/api/auth/google`, có CSRF cookie/token và nonce. Với chế độ popup callback này không dùng OAuth authorization-code redirect URI. Authorized JavaScript Origin cần khai báo đúng `http://localhost:18181`; không thêm đường dẫn `/api`. Không tạo/sửa OAuth client của ShopQuery.

Live test đã phát hiện hai lỗi: mở frontend qua 127.0.0.1 khác APP_ORIGIN và token Google bị verifier báo clock_early với skew 0. Giao diện nay chuyển về origin chuẩn trước Google Login; backend vẫn từ chối origin khác. Verifier dùng dung sai iat/exp 10 giây của google-auth, sau đó app vẫn kiểm exp còn hiệu lực, aud/iss/sub/nonce. Unit test dùng chữ ký RSA thật, chỉ mock nguồn certificate: +5 giây chấp nhận, +60 giây/expired/tampered signature/wrong nonce từ chối. Certificate request timeout 5 giây; lỗi mạng trả 503 riêng; diagnostics chỉ log reason cố định, không log token/claims. Không thay đổi đồng hồ Windows.
