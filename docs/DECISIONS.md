# Quyết định và kiểm tra tiền triển khai ChatSAR

Bổ sung root cause critical31/10: guard trước chỉ tìm giá trị có trongDB nên model có thể bỏ so sánh với giá trị chưa tồn tại. validate_structure và helper explicit_text_mentions dùng tên/alias cột + cú pháp EQ tường minh (có quote hoặc ranh giới câu); không sinh/vá filter. Cùng helper nối vào payload, unitđa-schema/API-PG beforeexecute và modelretestNULL. Đây là grammar giới hạn, không semantic oracle. Historicalcritical response giữ nguyên; nguồn cuối6/7FAILfollowup, không đạt acceptance.

## Root-cause repair — 31/10/2026

Chủ dự án cho phép review bảo thủ đúng HTTP503 a4755acf-0039-4928-890e-0f57b6b4322d trong grant69d37b9b-fd6d-4296-9189-9fb5303b46a1; không cấp grant/cap/budget mới. Toàn row gốc giữ nguyên, tokens/costNULL và reserve0.0141532USD; audit riêng qua role admin. Quyền tối đa95 Codex/100tổng, giữ5mới và9cũmanual. Baseline127rows đã khóa local trước live.

Thiết kế tối thiểu: mở rộng provider_usage_reviews hiện hữu, kiểm toàn snapshot JSONB với row hiện tại (bao gồm ID/provider/grant/reserve/status/error/usage); HTTP503 còn cần direct response hook và PROVIDER_TEMPORARY. HTTP400 đã review vẫn tương thích. Exception SDK có status không được tự ghi thành bằng chứng HTTP; chỉ hook/direct response mới lưu http_status. Admin CLI `python -m operations.usage_review` mặc định preview, apply so lại snapshot trong advisory lock chung, UNIQUE chống trùng, tối đa3review503/grant, cap/budget giữ nguyên. API không có admin credentials/quyền ghi reviews. Công cụ quản trị thay SQL thủ công cho lỗi sau; vẫn cần quyền/evidence cụ thể, không tự duyệt mọi lỗi.

Không thêm automatic retry: một reservation/một HTTP, chặn hidden SDK retry. Sau phản hồi429/500/503 có cooldown60s từ thời điểm hoàn tất; hai503liền nhau tăng300s. Cooldown lưu theo ledger nên qua restart, không cache/circuit framework mới. Yêu cầu mới sau cooldown là thao tác có chủ đích, không replay idempotency key cũ. Timeout/network/504/unknown chưa review vẫn dừng; 400/401/403 không retry. Google hướng dẫn backoff khi retry nhưng không chứng minh error miễn phí; retain_full_reserve là chính sách nội bộ của chủ dự án, không billing reconciliation.

Follow-up có repro mới: model lấy literal cũ dài hơn, guard chặn. Payload thêm current_value_mentions bằng mentioned_phrases hiện có trên vocabulary bounded đã kiểm quyền: giúp phân biệt giá trị được nhắc hiện tại với vocabulary/context cũ. Không prune/sửa context, không thêm/vá filter hoặc candidate sau model, không engine thứ hai. Regression prefix/ID/nhiều vị trí và live trước-sau báo riêng.

Audit90annotations khóa trong annotation_review.json, giữ nguyên semantic.json/gold/checksums. Một adjudication SUM-only của câu tháng9 báo cả original_reference_pass và adjudicated; SQL viết tay kiểm PG trước live. Hai schema mới museum/bakery gồm10cases khóa cùng SQL/metadata/expected bằng generalization_checksums trước chạy model; người viết biết labels, không gọi blind external. Không dùng expected trong payload, không tuning trên output held-out.

Nguồn chính thức đã đọc trước sửa: [Gemini troubleshooting](https://ai.google.dev/gemini-api/docs/troubleshooting), [API errors](https://ai.google.dev/gemini-api/docs/api-errors), [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits), [structured output](https://ai.google.dev/gemini-api/docs/structured-output). 503 là dịch vụ quá tải; 429 có rate/quota; 504 deadline khác timeout không response. JSON Schema không chứng minh semantic correctness. Runtime pin google-genai2.34.0/httpx0.28.1 giữ nguyên; SDK thực qua MockTransport/socket cấm kiểm một dispatch cho400/401/403/429/500/503/504/timeout/disconnect. Không đổi dependency/model.

## Tiếp tục khắc phục và nghiệm thu — quyền mới 30/10/2026

Chủ dự án yêu cầu sửa hết lỗi còn lại, xác nhận thêm tối đa100HTTP Gemini/trần dự phòng bổ sung1.50USD. Đây là quyền mới sau checkpoint2669ea4, không sử dụng9lượt cũ đã bàn giao thủ công. Baseline PostgreSQL104rows(Gemini99/Knowledge5), grant cũ91used/reserve1.2290194USD. Giữ ledger/reviews/keys/flags, Knowledge/LlamaParse/BGE mới0; tối đa95lượt Codex trong phần bổ sung, giữ5lượt mới và9lượt cũ cho chủ dự án. Chỉ điều chỉnh cap local có kiểm soát trước live; dừng nhóm khi lỗi hệ thống/unknown usage, không retry tự động.

Chẩn đoán: profile AI Setup chỉ có thống kê, không có vocabulary nên không thể đề xuất ánh xạ ngôn ngữ có căn cứ; query guard đúng khi từ chối dịch chưa được xác nhận. Bổ sung consent riêng để gửi vocabulary giới hạn20giá trị/cột TEXT/boolean, không gửi dòng; AI chỉ đề xuất alias/mapping từ đó, vẫn review/validate toàn bảng và owner confirm trước publish. Không nới literal guard hoặc tự thêm mapping sau khi model query. Ranking dùng projection tối thiểu(identifier+tiêu chí+đầu ra được hỏi), order phụ identifier ổn định; câu hỏi hiện tại thay điều kiện cùng cột của context, không tự mở rộng literal. Sửa tổng quát trước canary, không chèn tên dataset/câu benchmark vào production. Gold/hai plan giữ nguyên; lần kiểm với catalog đã review phải ghi rõ điều kiện khác baseline, không sửa4FAIL lịch sử thànhPASS.

## Trang chủ khách và header — quyền mở rộng 30/10/2026

Chủ dự án yêu cầu lần đầu truy cập/sau logout mở trang chủ, ô account có Đăng nhập dẫn sang trang login; xác nhận khách được upload CSV/XLSX và hỏi AI đầy đủ nhưng reload mất dữ liệu/chat. Đây là ngoại lệ mới cho gate Google bắt buộc trước mọi thao tác; không tắt auth/owner hoặc dùng token Google giả. Hai plan gốc giữ nguyên, không Phase2. Chi phí không cấp thêm:9lượt còn lại đã bàn giao cho chủ dự án, Codex chỉ kiểm mock/offline/browser không generation.

Quyết định tối thiểu: principal guest thật, token ngẫu nhiên chỉ trong bộ nhớ trang, không cookie/localStorage để khôi phục phiên khách. Dùng cùng workspace/ingestion/catalog/compiler/chat/provider quota hiện hữu; dữ liệu khách lưu tạm server để xử lý và bị dọn khi kết thúc trang, có TTL/reaper trong API để xử lý đóng tab/network không gửi cleanup được. Không một query engine/local giả khác, không hứa hủy HTTP model đang bay; quota/ledger giữ dù user reload. Cleanup chỉ owner provider=guest đã hết phiên, giữ toàn bộ Google và provider ledger. Login Google giữ verify/nonce/CSRF/cookie cũ. Chủ dự án xác nhận login mở dữ liệu tài khoản và không chuyển phiên khách hiện tại; cleanup chỉ dọn guest, không nhập vào tài khoản khác.

Header screenshot xác minh focus outline của select sát title khi không có gap, không phải dữ liệu đè DOM. Tạo hai dòng có gap6px, select28px co theo chữ, bỏ nền/viền theo yêu cầu tiếp nối; outline bàn phím2px/offset1px, giữ context dưới title; kiểm focus và bốn breakpoint sau build.

## Usage review, quyền nguồn ready và nghiệm thu mới — 30/10/2026

**Kết quả:** một pilot lookup thiếu projection đã FAIL/dừng; sửa tổng quát record phải project EQ lookup columns và chỉ thêm một lần hướng dẫn cấu trúc, không thêm cột sau model. Candidate sau khóa đạt canary4/4, cùng26ca baseline26/26 và printing6/6 chưa dùng model trước đó. Đã chuyển QueryRequest vào một đường runtime; wrapper process canary đã bỏ. Compiler/query.py, parser/tabular.py, setup/publish logic và hai plan/gold giữ nguyên. Mở rộng qua HTTP phát hiện3 false refusals (lúa→rice, chưa thu hoạch→false chưa có mapping; follow-up3→quận3) và top hotel output dư cột/thiếu order phụ. Giữ4FAIL, dừng từng nhóm, không tiếp tục tuning dựa held-out hay sửa expected. Bản hiện hành NOT_ACCEPTED. Không lấy việc guard ngăn sai literal làm NL PASS.

Yêu cầu mới “HOÀN THIỆN GIAI ĐOẠN 1, SỬA USAGE/DATA PERMISSION, SỬA UI CUỐI” cho phép chính sách hạch toán bảo thủ có audit khi thiếu usage thật. Thay điều kiện khóa vĩnh viễn cũ trong đúng phạm vi này; không cấp thêm ngân sách. Giữ grant hiện hữu: còn tối đa45 Codex/50 tổng, reserve toàn đợt<=1.50USD, ít nhất5 lượt cho chủ dự án; Knowledge/LlamaParse/BGE mới=0. Hai plan/gold không sửa, không merge/Phase2.

Thiết kế nội bộ: bảng provider_usage_reviews chỉ admin INSERT, app chỉ SELECT, theo từng usage_id và snapshot status/model/error/dispatch; chỉ lỗi Gemini HTTP400/PROVIDER_SCHEMA đã có chứng cứ. Giữ usage/costNULL và reserved_cost gốc, toàn reserve tiếp tục tính cap; đây là khoản dự phòng được chấp thuận, không phải xác nhận hóa đơn hoặc biết cost thật. Không tự duyệt lỗi mới, mismatch hoặc request đang bay; unknown mới tiếp tục chặn. Không chọn xóa/reset ledger hoặc coi HTTP400 miễn phí. Bổ sung lưu HTTP status an toàn cho lượt mới; usage đã nhận trước lỗi JSON vẫn dùng để tính estimate có căn cứ.

Root cause quyền dữ liệu: consent setup có chủ đích chỉ một lượt metadata; sharing_providers dành query độc lập. UI cũ chỉ cho thay quyền khi confirm, revision ready không confirm lại được, nên private ready chưa chia sẻ bị kẹt ở DATA_PERMISSION_REQUIRED dù user muốn cấp quyền. PATCH sharing owner/session/CSRF cho đúng revision ready, audit trước/sau và request_id; không sửa classification/schema/rows/checksum. Khóa revision thống nhất với send, chặn đổi quyền khi pending; thu hồi áp dụng lượt kế tiếp, không hứa xóa dữ liệu đã gửi. Không bật hàng loạt hoặc đổi private sang synthetic.

QueryRequest vẫn candidate trong harness riêng process nhưng dùng cùng adapter/guard/compiler/PG/API, không thêm production flag/query engine. Canary khóa trước4ca regression: lookup đủ mã+phí, MIN scalar, COUNT_ROWS+SUM hai mốc timestamp, thiếu tỷ giá CLARIFY; dừng nhóm khi FAIL/unknown. Chỉ đề xuất đổi runtime nếu canary và tập độc lập đủ tốt, không suy consistency offline thành semantic PASS. UI workspace thành context line dưới title chat; hai nhãn ổn định Nguồn & xử lý/Truy vấn SQL, không dựng SQL cho lịch sử hoặc lượt bị chặn.

Nguồn đã kiểm lại: [Gemini billing](https://ai.google.dev/gemini-api/docs/billing) chỉ cách theo dõi billing, không xác nhận miễn phí cho lỗi cụ thể; [Interactions](https://ai.google.dev/gemini-api/docs/interactions-overview) về state/store; [structured output](https://ai.google.dev/gemini-api/docs/structured-output) chỉ bảo đảm hình thức và cần app kiểm nghĩa; [PostgreSQL row locks](https://www.postgresql.org/docs/17/explicit-locking.html) làm căn cứ serialize quyền/send. Không lấy các docs thay số đo ChatSAR.

## Câu trả lời tự nhiên, SQL và chẩn đoán — 30/10/2026

Chủ dự án giao “TEXT-TO-SQL, NATURAL ANSWERS, SQL TRANSPARENCY & FINAL UX”. Baseline32ffde9 sạch, CI push/PR PASS,3services healthy; ledger63 (58/5),HTTP400 usage/costNULL/dispatch1/reserve0.0137353USD không đổi. Prompt không cấp quyền reconciliation bảo thủ hoặc budget mới; candidate vẫn offline và canary/benchmark BLOCKED. Không sửa hai plan/gold/keys/ledger, không thêm engine/dependency/model call. Canary khi đủ quyền phải khóa4ca development: lookup đủ mã+giá trị, MIN scalar, COUNT_ROWS+SUM với hai mốc thời gian, thiếu tỷ giá CLARIFY; mỗi ca1dispatch, dừng FAIL/unknown, đối chiếu typed plan/rows/status chứ không chỉ số trùng. Không chạy các ca đó trong nhiệm vụ khi guard chưa mở hợp lệ.

Natural answers dùng một composer tất định thay block render trong conversation.py: phép tính từ plan đã bind, labels từ aliases owner đã xác nhận hoặc tên cột dễ đọc, không suy dịch room_charge sang nghiệp vụ nếu không có metadata. Description không dùng như tên chắc chắn. COUNT_ROWS gọi bản ghi, không tự suy thực thể từ tên file/grain prose. Format Decimal theo chuỗi, dấu phẩy thập phân, không float, không thêm đơn vị thiếu; NULL aggregate không thành0. Multi/group/ranking giữ bảng và nói giới hạn thực. Đây là thiết kế nội bộ, kiểm đa schema/result shapes; không có thêm LLM.

SQL evidence additive trong envelope JSON hiện hữu, không migration: snapshot statement SQLAlchemy chính thức bằng PostgreSQL dialect và render_postcompile (giữ placeholders, không literal_binds/params values). [SQLAlchemy](https://docs.sqlalchemy.org/en/20/faq/sqlexpressions.html) xác nhận compile theo dialect và parameter binding; [PostgreSQL17 aggregates](https://www.postgresql.org/docs/17/functions-aggregate.html) phân biệt COUNT/NULL/SUM(empty); [Python Decimal](https://docs.python.org/3.11/library/decimal.html) làm căn cứ giữ precision. Không format thành SQL khác để execute; executor tiếp tục dùng cùng Select. SQL string chỉ đọc theo message/result owner, không trace/public log; lịch sử thiếu SQL báo chưa lưu, không compile lại.

Theo dõi bước thực: authorization/catalog/provider preparation/provider call/proposal parse/semantic validation/SQL compilation/execution/composition/persistence. compile_query hiện bind+build Select; semantic_validation giữ đúng tên cho bước này, compilation là lúc dialect compile string. Execution có callback ngay trước statement execute để không gán đã chạy khi grounding/connection thất bại. Checkpoint owner-scoped trước execute giữ SQL khi process chết; recovery báo unknown cho execution đang chạy, không tự retry. Thời gian backend đến trước lần lưu cuối ghi đúng phạm vi, checkpoint nằm trong execution pipeline, không có số đo persistence riêng; không bịa tổng HTTP/browser hoặc cộng spans lồng nhau. ProviderError chỉ thêm stage/provider/model metadata an toàn, không đổi guard/instructions/contract.

UI tinh chỉnh trong CSS/React hiện hữu, không redesign: một cụm newchat/menu, workspace lên trên search, icons nhỏ menu+, selector gọn, hai button source/error và SQL/SQL-status; panel collapsed mặc định, một panel/message, Escape và focus, SQLpre scroll. Dữ liệu cũ đọc được với missing fields; không sửa lịch sử để làm bằng chứng mới.

## Hoàn thiện chất lượng và UI — 30/10/2026

Kết luận gate trước bàn giao: không đủ chứng cứ Gemini compatibility cho QueryRequest do usage bị chặn. Đã giữ candidate và tests offline, phục hồi INSTRUCTIONS/generate_proposal production đúng hợp đồng đã chạy thành công. Không thêm feature flag hoặc hai runtime, không thử generation để mở gate. UI/API mới vẫn triển khai độc lập. Các mô tả candidate dưới đây không phải runtime đã nghiệm thu. Bốn lỗi model cũ chưa được tuyên bố khắc phục live.

Phạm vi mới do chủ dự án giao: hoàn thiện SQL, lịch sử theo revision, đổi tên/xóa chat, hồ sơ local và composer tối giản. Không sửa hai plan gốc, compiler, parser, Setup/publish, OAuth core hoặc quyền cloud. Baseline cf882a2 sạch, PR1 draft, CI đạt. Ledger vẫn 63 (58 Gemini/5 Knowledge); HTTP400 d10d5f23-d15d-4c9e-8e21-37e67b510b1c thiếu usage, không reconciliation bằng giả định. Chưa có chứng cứ billing theo request nên giữ USAGE_UNKNOWN, không generation mới.

Nghiên cứu trước thay đổi: [RESDSQL](https://ojs.aaai.org/index.php/AAAI/article/view/26535) tách schema linking và skeleton; [RAT-SQL](https://aclanthology.org/2020.acl-main.677/) nhấn mạnh liên kết câu hỏi/catalog; [BIRD](https://proceedings.neurips.cc/paper_files/paper/2023/hash/83fc8fab1710363050bbd1d4b8cc0021-Abstract-Datasets_and_Benchmarks.html) nhấn mạnh giá trị nguồn và kiến thức ngoài; [Spider2](https://proceedings.iclr.cc/paper_files/paper/2025/hash/46c10f6c8ea5aa6f267bcdabcb123f97-Abstract-Conference.html) cho thấy benchmark đơn giản không đủ chứng minh tác vụ thực. Không lấy số paper làm accuracy ChatSAR, không tích hợp model/framework từ các repo nghiên cứu.

Lựa chọn nội bộ: một request có result_shape (record/list/scalar/group/ranking) và required_columns, cộng điều kiện dạng danh sách node hậu thứ tự với child indexes. Chuyển lossless sang Predicate/QueryPlan hiện hữu; không suy/bổ sung literal hoặc filter. Kiểm cây dùng mỗi node đúng một lần, con đứng trước cha, không orphan, sâu <=8, <=100 nodes. Scalar không còn trường result_mode độc lập để model gắn nhầm top; ranking bắt buộc order. Record giữ identifier và đủ required_columns, không aggregate. Các guard này chỉ kiểm nhất quán, không chứng minh model đã khai đủ ý định. Compiler/binder vẫn là nguồn kiểm quyền/kiểu/SQL duy nhất.

Không chọn: schema anyOf đệ quy đã HTTP400; parser bằng regex ngành; thêm lượt LLM hoặc engine khác. [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output) chỉ bảo đảm cấu trúc, yêu cầu app kiểm nghĩa và cảnh báo branching/depth. Dạng phẳng giảm recursion nhưng tương thích model thật vẫn BLOCKED tới khi usage được đối soát. Bốn lỗi lookup/MIN/time COUNT+SUM/FX là lỗi planning; chưa có bằng chứng compiler sai. Không đổi gold để hợp thức hóa.

UI dùng React/CSS và native dialog hiện hữu, không dependency mới. Menu button theo [WAI-ARIA](https://www.w3.org/WAI/ARIA/apg/patterns/menu-button/), có focus, Escape, touch. API bổ sung chỉ owner/session/CSRF, xóa phạm vi workspace hiện tại, transaction xóa results→messages→conversations; khóa workspace trước mutation, chặn pending. Không xóa dataset/workspace/ledger. Hồ sơ chỉ ChatSAR, không gửi sang Google/provider/tracing. Migration additive, bảo toàn lịch sử; rollback code giữ cột mới.

Tham khảo read-only [README Shopquery-AI](https://github.com/MinhHoang1403/Shopquery-AI/blob/main/README.md) (maintenance-ended 29/10/2026) và [Sidebar](https://github.com/MinhHoang1403/Shopquery-AI/blob/main/frontend/src/components/Sidebar.tsx) để đối chiếu vị trí history/account/menu. Không copy code, không dùng backend/runtime của ShopQuery hoặc nhận các tests của dự án đó thành bằng chứng ChatSAR. Không tích hợp thư viện OSS mới, không tải weights. Dạng list_all giữ result_mode=all để không làm hồi quy guard/truncation danh sách đầy đủ.

Đối soát usage: [Interactions](https://ai.google.dev/gemini-api/docs/interactions-overview) và [logs](https://ai.google.dev/gemini-api/docs/logs-datasets) mô tả lưu/retrieve khi store=true; app đã gửi store=false, không có interaction ID cho lỗi. [Billing](https://ai.google.dev/gemini-api/docs/billing) chỉ đường AI Studio/Cloud Billing, không chứng minh HTTP400 miễn phí. Không đổi ledger, không mở guard; cần chứng cứ usage/billing thực từ project hoặc quyết định riêng của chủ dự án trước live.

## Quyền và thiết kế ổn định hiện hành — 30/10/2026

Chủ dự án cấp tối đa 100 HTTP Gemini bổ sung, Codex tối đa 95, dành ít nhất 5 cho kiểm thử thủ công, dự phòng 1.50 USD; Knowledge/LlamaParse/BGE = 0. Baseline PostgreSQL 02:17:55 UTC là 13 reservations (Gemini 8/Knowledge 5), không đổi lịch sử. Được điều chỉnh quota local cần thiết nhưng không API keys; mỗi reservation vẫn chặn dispatch thứ hai. Chưa gọi live trong baseline.

Quyết định nội bộ trước sửa: giữ SetupProposal đầy đủ cho review/publish và lịch sử; contract gửi model chỉ chứa đề xuất metadata/thay đổi theo column ID. Backend ghép vào local profile theo thứ tự nguồn rồi dùng validate_rows chính thức. Vấn đề nguy hiểm bị từ chối; metadata chưa có căn cứ và ngày mơ hồ cần review, không tự publish. Không giữ contract cũ bắt model sao chép các bất biến, không bỏ validation. Khóa ghép phải kiểm uniqueness toàn tuple bằng validate_rows, thay kiểm từng cột riêng (tái hiện offline); chưa khẳng định đây là nguyên nhân lượt hotel cũ.

Quota đợt nghiệm thu lưu PostgreSQL, liên kết usage với grant có baseline/cap/ngân sách; cấu hình runtime chọn grant, default không grant/cloud OFF và per-provider 10. Grant của Codex cap 95 trước khi chuyển phần còn lại cho thủ công; toàn đợt không quá 100. Dự phòng từng request bị trừ vào trần 1.50, không lấy chi phí ước tính thấp hơn để mở thêm quota. Ghi số dispatch trước transport; lỗi/unknown usage không được tự coi miễn phí. Migration additive, không DROP/rewrite dữ liệu; rollback code giữ cột/bảng quota và app cũ vẫn đọc được.

Ngày: 29/10/2026. Baseline: `c05f26b1a301e91e8ea6ddaadedb0e1ed03b735d`.
Người cấp quyền: chủ dự án, yêu cầu bắt đầu preflight và Giai đoạn 1 trong hội thoại.

## Phạm vi và trạng thái gate

- Được triển khai theo kế hoạch F1 → F2 → F3 → F4, trên `feature/sql-foundation`; chưa được merge hoặc sang Giai đoạn 2.
- Yêu cầu mới thay thế giới hạn chỉ thiết lập GitHub trước đây. Không làm lại phần GitHub đã hoàn thành.
- **Design review:** baseline hợp đồng/ownership/layout/benchmark đã cụ thể hóa theo kế hoạch. Chỉ đạo mới cho phép hoàn thiện F1 rồi F2 và phần độc lập F3/F4 qua test harness dù Google live BLOCKED. Nghiệm thu live và Phase 1 tổng thể vẫn cần bằng chứng; không giả PASS.
- Theo chỉ đạo tiếp tục phần độc lập khi thiếu điều kiện bên ngoài, được chuẩn bị hợp đồng, oracle/fixtures và nền tảng F1 không gọi provider. Đây không phải nghiệm thu đầy đủ Giai đoạn 1; chỉ chuyển milestone khi acceptance tương ứng thực sự đạt.
- Không đổi kiến trúc đã chọn. Các quyết định chi tiết dưới đây là cụ thể hóa kế hoạch, không phải kết quả phần mềm đã chạy. Kết quả đo được ghi tại `PREFLIGHT.md`.

## Các quyết định nền tảng

| Quyết định | Lựa chọn dùng | Hai phương án không chọn | Căn cứ, chi phí/rủi ro và kiểm thử |
|---|---|---|---|
| Kiến trúc | React/TypeScript/Vite + FastAPI/Pydantic + SQLAlchemy Core + PostgreSQL/pgvector, một Compose | Microservices; thêm DB/agent framework | Đúng kế hoạch; một pipeline SQL; kiểm tra tích hợp thật |
| Ownership | Một owner/workspace; principal và catalog binding do server quyết định | Tin owner từ client; dựa hoàn toàn vào quyền SELECT chung | Reader dùng chung không tự cô lập tenant; bắt buộc negative tests ở API trước nghiệm thu |
| Dữ liệu vật lý | Schema `data`, bảng revision với identifier do server sinh; metadata trong `app` | Tên bảng từ filename; schema-per-user | Cần POC PostgreSQL về quyền, transaction rollback và publish trước F3 |
| DB roles | Admin/migration riêng; app writer; reader SELECT không owner/superuser/BYPASSRLS | API chạy superuser; LLM chọn role/schema | App không nhận mật khẩu admin. Reader có timeout và transaction chỉ đọc; tests quyền thực |
| SQL | LLM chỉ đề xuất typed plan; server bind rồi SQLAlchemy Core compile | Thực thi raw SQL model; nhiều generator/fallback | Strict structure không chứng minh hiểu đúng câu hỏi; oracle độc lập là bắt buộc |
| Literal/kiểu | Giữ raw phrase + typed value + provenance; Decimal, TEXT ID, NULL rõ | Ép float; tự chuẩn hóa giá trị mơ hồ | Cases quận 3/3, 0007/7, COUNT và precision |
| Google | Web Client ChatSAR riêng, GIS POST + double-submit CSRF, session DB | Dùng client/session ShopQuery; email làm khóa | Backend verify chữ ký/iss/aud/exp/sub; live login cần cấu hình thực |
| Cloud | OFF mặc định; chỉ bật theo quyền/hạn mức người dùng điền; không fallback ngầm, chỉ synthetic | Suy ra free tier; tự chọn ngân sách dương | Chủ dự án đã cấp smoke tests; cấu hình hiện tại 10 requests tổng và 10 USD, thấp hơn mức 10/provider; kết quả ở PREFLIGHT |
| Benchmark | SQL oracle viết tay + expected cố định + đối chứng Decimal; tách development/regression/held-out | Sinh gold bằng compiler; sửa expected theo model | Khóa checksum trước compiler/tuning. Held-out bị dùng để sửa phải chuyển sang regression |
| Hạ tầng | Một Compose project `chatsar`; tài nguyên/volumes riêng; bind localhost | Copy source/test stack; tái sử dụng DB/volume dự án khác | Kiểm tra ports cả container đang dừng; không restart/dọn dịch vụ khác |

Các chi tiết trên do Codex đề xuất trong phạm vi kế hoạch được chủ dự án cho triển khai ngày 29/10/2026; không ghi nhận có một lần phê duyệt riêng từng chi tiết hoặc benchmark threshold.

F4 cụ thể hóa bằng một QueryPlan/binder/compiler, một adapter lựa chọn provider mỗi lượt và read-only reader engine. Các biện pháp coverage chỉ là guard nội bộ; oracle/gold độc lập mới dùng để chấm nghĩa. Schema provider được chiếu bỏ maxItems lồng nhau và yêu cầu properties đầy đủ theo giới hạn constrained decoding chính thức; server giữ nguyên caps. Kiểm thử HTTP giả lập phát hiện SDK 2.34.0 đổi attempts=0 thành 1 rồi bridge Interactions hiểu là retry: thêm chốt một HTTP dispatch trong client mỗi reservation, không sửa dependency/vendor SDK và không gọi live thêm để thử.

## Điều kiện bên ngoài và phạm vi bị chặn

| Điều kiện | Trạng thái trước triển khai | Tác động |
|---|---|---|
| Google OAuth Client/origin riêng | Chủ dự án đang tạo, chưa có cấu hình local để xác minh | Real Google E2E và nghiệm thu đầy đủ F2 BLOCKED |
| Knowledge base URL/protocol/auth/allowlist | Chủ dự án có URL; chưa cung cấp file local; không giả định OpenAI-compatible | Probe từ container và model-live BLOCKED |
| Langfuse project/keys ChatSAR | Chủ dự án đang tạo; server hiện hữu đang dừng | Không restart server; tracing live BLOCKED, không chặn health nền tảng |
| Gemini model+SDK+schema live | Tài liệu có model; account access chưa thử; budget 0 | Model-live BLOCKED, không đổi model |
| LlamaParse/embedding/BGE inference | Chưa benchmark; không thuộc triển khai Phase 1 | Chỉ inventory; không tải model/triển khai Phase 2 |
| Ngưỡng latency và chất lượng | Theo §19 là đề xuất; chưa có baseline và phê duyệt riêng | Báo số đo, không tự công bố release PASS |

## Nguồn đã đối chiếu

Quyền bổ sung ngày 30/10/2026: chủ dự án đồng ý tối đa 3 HTTP requests Gemini/trần 0.06 USD cho đúng kế hoạch AI Setup hotel, hotel SUM, maintenance SUM; giữ cap 10/provider, .env và ledger. Chỉ sử dụng một lượt: JSON hợp lệ nhưng setup bị backend từ chối, đã dừng theo điều kiện. Ledger 13 (Gemini 8, Knowledge 5); không tự dùng hai lượt còn lại sau FAIL. Chi tiết và giới hạn chẩn đoán ở PREFLIGHT; không đổi prompt/validator khi chưa có bằng chứng nguyên nhân cụ thể.

## Hoàn thiện Giai đoạn 1 — Workstream A, 30/10/2026

Chủ dự án phê duyệt phạm vi trong yêu cầu “FINAL PHASE 1 IMPROVEMENT & ACCEPTANCE”: metadata nghiệp vụ đã xác nhận, value grounding, phát hiện cắt kết quả, AI Smart Data Setup và UI sáng xanh dương. Không sửa hai kế hoạch gốc. Giữ feature/sql-foundation và PR #1 nháp; không merge/sang Giai đoạn 2. Không có quyền generation mới: ledger lịch sử 12 reservations vẫn giữ nguyên.

Baseline exact SHA `40be61a952eae81aba7a7bf02d09d5cb8e32cd0f`, local=remote, working tree sạch; CI push/PR SUCCESS; web/api/db healthy. Chạy lại: 65 unit, 18 integration (7 auth + 11 datasets/query/chat), 25 independent SQL oracle, 10 manifest/DB privilege tests PASS; mypy/ruff và frontend typecheck/build PASS.

| Tầng | Bằng chứng và nguyên nhân | Thay đổi tối thiểu cần kiểm thử |
|---|---|---|
| Catalog/schema | ColumnReview chưa có description/aliases/role/mapping; prompt chỉ có name/type/unit | Bổ sung trong JSON columns hiện hữu; metadata bảng và quyền chia sẻ bằng migration additive, không sửa physical data |
| Value grounding | Binder chỉ so typed raw phrase/candidate, chưa kiểm giá trị TEXT có trong nguồn | Tra cứu bounded bằng reader trên revision được cấp quyền; exact hoặc mapping đã xác nhận, không fuzzy |
| Query planning/validation | coverage sao chép spans của cùng model; prose metric/population không ràng buộc phép tính | Bỏ trường trùng lặp khỏi schema provider; kiểm các tín hiệu cấu trúc hỗ trợ và giá trị đã phát hiện độc lập; không tuyên bố chứng minh mọi nghĩa tiếng Việt |
| Execution/composition | compiler LIMIT trước fetch nên không biết có dòng thứ N+1; answer luôn answered | Probe N+1, cắt ở server và trả partial/truncated cho safety cap; phân biệt top N có chủ đích |
| Provider | Hotel timeout 30 s; logistics provider 29.16 s, SQL 22.36 ms; deadline 60 s chưa live | Giảm schema/prompt lặp, giữ 60 s và một dispatch; không thêm lượt LLM hay tự retry |
| Setup/UX | Người dùng đang phải review cấu hình kỹ thuật từng cột; chưa có AI setup | Local profile → đề xuất có quyền → validate toàn bảng → user confirm → publish hiện hữu; lỗi provider vẫn cho local review |

Một lượt model là lựa chọn mặc định; so sánh hai cấu trúc bằng fixture offline chỉ đo được tính nhất quán/độ lớn schema, không suy ra accuracy, tokens hoặc latency model thật. Hai lượt cần bằng chứng live tốt hơn và ngân sách riêng nên chưa được chọn. Mục tiêu 90 semantic scenarios là bộ đánh giá, không phải quyền gọi cloud 90 lần. Case đã dùng phát triển không được gọi held-out.

Workstream D: tham khảo đọc Sidebar/ChatHeader của Shopquery-AI trên GitHub để hiểu new chat/history/data manager/account/source selector; không copy code hoặc tác động runtime của dự án đó. ChatSAR dùng CSS/React hiện hữu, không thêm UI framework. Authentication, Workspace, Chat, Result, Datasets, AIReview và DTO tách theo trách nhiệm. Native dialog có focus/ESC; sidebar, composer, review kỹ thuật thu gọn, quyền metadata/provider riêng và Gemini mặc định. Có 6 tests SSR/DTO bằng node:test + Vite sẵn có, không mở server/test runtime thứ hai. SSR không thay thế browser interaction/responsive QA.


- PostgreSQL privileges: https://www.postgresql.org/docs/17/ddl-priv.html
- SQLAlchemy Core SELECT: https://docs.sqlalchemy.org/en/20/core/selectable.html
- Pydantic strict validation: https://docs.pydantic.dev/latest/concepts/strict_mode/
- Google ID token/CSRF: https://developers.google.com/identity/gsi/web/guides/verify-google-id-token
- Google-auth clock_skew_in_seconds (10 giây là lựa chọn nội bộ đã kiểm thử, không phải khuyến nghị mặc định của Google): https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.id_token.html
- Docker health dependencies: https://docs.docker.com/compose/how-tos/startup-order/
- Gemini model (không chứng minh account access): https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite
- Langfuse compatibility: https://langfuse.com/self-hosting/upgrade/versioning
- Gemini JSON Schema và giới hạn grammar: https://ai.google.dev/gemini-api/docs/structured-output
- Gemini Interactions/store/continuation: https://ai.google.dev/gemini-api/docs/interactions-overview
- Gemini pricing dùng để ước tính, không phải hóa đơn: https://ai.google.dev/gemini-api/docs/pricing
- Langfuse Observations API v2: https://langfuse.com/docs/api-and-data-platform/features/public-api
- PostgreSQL aggregate return types: https://www.postgresql.org/docs/17/functions-aggregate.html

Nguồn xác nhận cơ chế; lựa chọn lưu trữ, giới hạn và oracle là thiết kế nội bộ cần kiểm thử. Không lấy tài liệu làm bằng chứng runtime PASS.
