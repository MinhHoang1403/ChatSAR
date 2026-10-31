# Vận hành ChatSAR

## Quota đã áp dụng và luồng kiểm tiếp — 31/10/2026

Đã áp dụng grant_limits sau guest_sessions (10migrations). Chỉ thay hai CHECK của provider_grants, không sửa usage/baseline. Grant69d37b9b-fd6d-4296-9189-9fb5303b46a1 thực tế495requests/10USD, giữ5manual trong tổng500; .env global604/Gemini599/Knowledge5, flags/keys/globalbudget20khôngđổi. Không chạy authorize tạo grant khác hoặc reset ledger. Migration chạy lặp an toàn và không tự tăng quota; app vẫn chỉ SELECT grant/review. Evidence mở quota giữ snapshot199rows.

Đơn vị model gợi ý không tự áp dụng khi owner lưu before/after; owner nhập đúng unit ở chi tiết nếu cần. Xem header so sánh để kiểm units đã nhập. Cached proposal vẫn reuse0call, không dùng cache để vượt policy unit mới hoặc source binding. Kiểm live theo batch, giữFAIL/refusal và source fingerprint; không gộp source khác nhau thành accuracy. Không merge hoặc Phase2.

## Luồng dữ liệu mới và quyền500 — 31/10/2026

Chọn file tự chuẩn bị, xem trước/sau rồiLưu; không còn bấm phân tích/cấp quyền riêng. Cachedsetup tự mở, XLSX nhiều sheet chọn đúng trang. API normalization-preview dùng cùng validator với publish/toàn bảng, không callmodel. LỗiAI sẽ nói rõ dùng nhận diện từ file; không tự retry để tiêu credits. Nguồn mới được cấu hình cho2model theo policy owner, actualdispatch vẫn chọn một model/guard/cap; privategiữnguyên.

Owner vừa cấp trầntổng500requests/10USD dự phòng, giữ5manual. Một grant69d37b9b-fd6d-4296-9189-9fb5303b46a1 và ledger199/95used tại checkpointUI, không reset/newgrant/đổi keys. Chỉ tăngcap sau migration và audit snapshot đúng quyền mới; Knowledgecap5đãdùng5, Llama/BGEkhôngthêm. Các đoạn100/1.50 phía dưới là lịch sử, không phải ngân sách hiện hành sau áp dụng mở rộng.

## Vận hành audit503 — 31/10/2026

Không sửa usage/cost thành0, không đổi grant/reset ledger. `python -m operations.usage_review --usage-id UUID --grant-id UUID --model gemini-3.5-flash-lite --reserve DECIMAL --authority "Quyền cụ thể của chủ dự án"` chỉ preview. Sau kiểm đúng evidence/quyền, thêm `--apply` để ghi audit bằng chatsar_admin qua Compose db. API không nhận mật khẩu admin, không tự chạy công cụ này. Công cụ chỉ nhận verified HTTP503/error/dispatch1/UNKNOWN/fullreserve và snapshot nguyên vẹn, giới hạn3review503/grant; không phải bypass chung. Review trùng/mismatch/hết budget phải điều tra, không sửa trực tiếp bảng để vượt.

Lần gửi có chủ đích sau lỗi cần key mới, đợi cooldown60s (hai503liền300s). Không retry cùng key/pending; GET history trước khi quyết định gửi lại. Timeout/network/unknown thiếu response vẫn giữ gate. Không kết luận Google không thu phí; reserve tiếp tục tính đầy đủ. Lượt503lịch sử đã được chủ dự án cho phép audit, các phần dưới giữ lịch sử trước quyền31/10; xem đầuPREFLIGHT về số liệu hiện hành.

## Vận hành hiện hành sau đợt sửa — 30/10/2026

Live đang dừngUSAGE_UNKNOWN doHTTP503 mới a4755acf-0039-4928-890e-0f57b6b4322d, khôngphảilỗiconfigsource. Khônggọihealthmodel/retry/chuyểngrant hoặc thêmreviewHTTP400cho503. Giữtokens/costNULLvàreserve0.0141532USD. Quyềnmới thêm100calls/1.50USD,grant riêng69d37b9b-fd6d-4296-9189-9fb5303b46a1,max95Codex;đãdùng23,reserve0.3117407USD. Ledger127=122/5. Còn77mới và9cũmanual nhưng usagegate vẫn dừng; .env chỉđổi total/provider cap vàactivegranttheoquyềnmới,keys/flags/budgetglobalgiữnguyên. Không dùngquota còn đểtựbỏchặn.

AI Setup có thêmcheckbox gửi tốiđa20giátrịphânbiệt/cột để đềxuất cáchgọi; mặcđịnhtắt, cầnmetadataopt-in,khônggửidòng. Chủnguồnreview/confirmmappingtrướcpublish,quyềnhỏiGemini riêng. Không sửa nguồnGoogle thật đểbenchmark; bảngquality-ui.csv tổnghợp2rowsởkhônggian nghiệmthu củaaccountBgiữprivate/sharing[]. AccountA/historySQLgiữnguyên. BrowserhaiGoogleđãuserloginvàkiểm chuyểnidentity;chưaphải haiindependentprofilesđồngthời.

157unit/42integration/28evaluation/14frontend+types/build đãkiểm. Chạyquota/integration/acceptance tuần tự vìfixturesquotacórows tạmtácđộnggloballedgerassertion. Hai plan/goldgiữnguyên. Phase1NOT_ACCEPTED; xemđầuPREFLIGHT.

## Bổ sung hiện hành: phiên khách — 30/10/2026

Áp dụng migration guest_sessions sau usage_review trước build/start; readiness yêu cầu đủ9migrations. Trang chủ không còn yêu cầu login trước. Đăng xuất chỉ thu hồi session tài khoản, không xóa dữ liệu Google. Login từ khách mở dữ liệu tài khoản, không nhập guest. Guest token không được lưu bền phía trình duyệt; refresh tạo phiên sạch. Frontend pagehide/login gửi DELETE keepalive; server giới hạn token2giờ và reaper60giây dọn guest hết phiên, không chạm provider ledger hoặc Google. Pending setup/ingestion/model trì hoãn cleanup đến khi xong/recovery, không hủy hoặc replay HTTP đang bay. Nếu trình duyệt không gửi cleanup, dữ liệu tạm còn server đến TTL/reaper; không coi việc UI mất dữ liệu là chứng minh xóa vật lý ngay mọi tình huống.

Kiểm guest dùng mock provider, quota thực không tăng.9lượt còn lại dành chủ dự án, không gọi để smoke test guest. Khách vẫn phải cấp quyền hỏi đáp cho nguồn private và chịu cùng budget/provider guards. Không có public deployment hoặc quota vô hạn mới.40integration gồm6guest;14frontend,148unit/types/build PASS. Tổng Phase1 vẫn NOT_ACCEPTED.

**Hiện hành 30/10/2026:** Phase1 NOT_ACCEPTED. QueryRequest đã vào một runtime sau canary/so sánh/printing;4FAIL mở rộng còn giữ. Usage review admin theo từng usage_id giữ toàn reserve cho HTTP400 lịch sử, không sửa tokens/costNULL. Unknown mới vẫn chặn; app không tự approve. .env/keys/flags không đổi. Migration usage_review additive, app chỉ đọc provider_usage_reviews; không cấp INSERT/UPDATE/DELETE cho app/reader. Không tự thêm review vì chỉ thấyHTTP400: phải có chứng cứ/snapshot/quyền chủ dự án. Đây là dự phòng được chấp thuận, không là hóa đơn.

Đợt này41Gemini, tổng grant91/100, reserved1.2290194/1.50USD. Codex dừng generation tại91/95. Còn9lượt tổng, ít nhất5dành chủ dự án; đã chuyển cap grant95→100 khi bàn giao toàn9lượt cho chủ dự án trong đúng quyền100đã cấp; budget1.50USD/baseline/ledger giữ nguyên, Codex không gọi thêm sau bàn giao. Không dùng9lượt đó làm quyền tự test ở nhiệm vụ sau. Ledger104=Gemini99/Knowledge5; Knowledge/LlamaParse/BGE mới0.

Nguồn ready: Data Manager → chọn đúng file → Quyền hỏi đáp với mô hình → chỉ đánh dấu provider muốn cấp → Lưu quyền hỏi đáp; bỏ dấu và lưu để thu hồi cho lượt sau. Private giữ private. AI Setup consent không tự cấp query. Pending thì đợi hoàn tất trước đổi quyền. Nguồn synthetic vẫn theo chính sách kiểm thử đã xác nhận. Workbook-ui.xlsx kiểm thử đã trở lại sharing[]; chat Nghiệm thu quyền và SQL — 30-10 giữ result0.3và SQL thật sau restart, xem history không gọi model.

**Các mục bên dưới là lịch sử vận hành trước cập nhật này.** Dùng báo cáo đầu PREFLIGHT và CONTRACTS cho gate/usage hiện hành.

# Vận hành nền tảng ChatSAR

## Natural Answers/SQL evidence — 30/10/2026

Không migration mới, giữ7 migration/volumes hiện hữu. API lưu processing additive trong envelope: SQL placeholders/tên bind, không raw values; source snapshot, actual provider, durations và failed_stage. Owner kiểm ở conversation/result, không thêm API SQL tự do. Panel chỉ đọc history, không generate/compile/execute. Legacy thiếu SQL không backfill từ plan. Checkpoint trước execute có thể còn pending khi crash/final persist lỗi; recovery giữ SQL và chuyển in_progress→unknown, không replay. Không đổi unknown thành succeeded vì chỉ đọc thấy statement.

Composer tất định không thêm model calls. Live vẫn USAGE_UNKNOWN/ledger63=58Gemini+5Knowledge, không gọi để kiểm health/UI; quota còn không cấp quyền bypass. Runtime143unit/33integration/12frontend PASS, SQL provenance/persistence qua restart có provider mock trong process harness, không model E2E. Fresh Google/two-account/positive model SQL browser chưa nghiệm thu. Ảnh/evidence local ở artifacts, không đưa lên public. Trạng thái hiện hành và checklist đầu PREFLIGHT; các phần dưới là lịch sử vận hành.

## Bổ sung quản lý chat/hồ sơ 30/10/2026

Migration `chat_management` chạy sau provider_grants: thêm phone/interests và conversation.revision_id, backfill chỉ lịch sử có một revision. Không DROP hay thay bảng vật lý; rollback code giữ cột mới. API xóa chỉ chat/messages/results trong workspace được chọn, giữ nguồn/workspace/ledger. Chặn pending tại server; không dùng delete trên lịch sử thật để nghiệm thu. Hồ sơ chỉ principal hiện tại, không thay Google và không đưa vào prompt/trace. Composer dấu+ mở upload/tạo workspace/quản lý dữ liệu; model mặc định Gemini, Knowledge chọn tay, fallback UI đã bỏ. Không tự gọi model để kiểm giao diện khi USAGE_UNKNOWN.

## Trạng thái vận hành sau ổn định 30/10/2026

Runtime healthy, Phase1 NOT_ACCEPTED do chất lượng model còn thiếu, model-live BLOCKED_USAGE_UNKNOWN sau một HTTP400 không usage. Không gửi thêm model request để test health, không reset hoặc sửa usage/dispatch counter. Các đoạn quota cũ bên dưới là lịch sử; quyền mới tối đa100Gemini/1.50USD, Codex95, Knowledge mới0. Đã dùng50, còn trần45Codex/50tổng nhưng guard dừng live. .env giữ keys/flags/global budget20; globalcap113, Geminicap108, Knowledgecap5, active grant cap95/1.50USD. Giá trị trước thay đổi nằm trong artifacts/stabilization-quota.json; không coi global budget20 là quyền bổ sung.

Grant chỉ admin cấp, app chỉ đọc; migrations hiện gồm foundation/identity/datasets/conversation/catalog/provider_grants. Migration mới additive, rollback app giữ cột/bảng quota; không DROP hoặc sửa ledger. Default runtime vẫn cloudOFF/max0/budget0 và providercap10. Cần đối chiếu usage/billing lượt d10d5f23-d15d-4c9e-8e21-37e67b510b1c trước khi xem xét quyền tiếp tục; thiếu usage không phải chi phí0. Không tự bỏ guard vì còn quota.

Workspace nghiệm thu trên tài khoản hiện hữu giữ 3 file synthetic để chủ dự án xem: hotel-ui.csv ready, workbook-ui.xlsx(Data) ready/private không cloud, fallback-ui.csv needs_review/local. History “Tổng tiền phòng?” đọc lại300.15 không gọi model. Browser đã logout và reset viewport. Có thể kiểm login hai tài khoản/upload/local review độc lập trong khi live bị chặn. Không dùng test harness cleanup workspace Google thật này; harness chỉ dọn đúng UUID test owners do nó tạo.

Chỉ chạy tại root repository chính. Một Compose project `chatsar`, volume `chatsar_database`, không có test/staging project thứ hai. DB không publish port ra host. Web `http://localhost:18181`; API health `http://127.0.0.1:18081/health`. Kiểm tra lại port trước mỗi lần khởi động nếu môi trường đã thay đổi.

## Cấu hình local

`.env.example` chỉ chứa placeholder và provider OFF/budget 0. `.env` local bị Git bỏ qua. Mật khẩu DB/session phải ngẫu nhiên riêng cho ChatSAR. Không in `docker compose config` đầy đủ vì có thể lộ secrets; dùng `docker compose config --quiet` để kiểm tra cấu hình.

Chủ dự án có thể điền `GOOGLE_CLIENT_ID`, `KNOWLEDGE_BASE_URL`, các biến `LANGFUSE_*` vào `.env`, không gửi secrets qua chat. Google Web Client mới cần origin `http://localhost:18181`; cấu hình production HTTPS riêng sẽ được chốt sau. Không sửa OAuth client ShopQuery. Giữ nguyên flags enabled do người dùng đặt; mỗi tác vụ phải kiểm tra quyền và hạn mức riêng. Smoke tests Gemini/Knowledge tối đa 10 calls/provider hoặc giới hạn thấp hơn trong cấu hình. LlamaParse enabled không cấp quyền parse ở Phase 1. Không ghi đè .env.

## Các lệnh chính

```powershell
# Dependency phát triển trong cùng repository, theo lockfiles.
uv sync --project backend --frozen
npm.cmd ci --ignore-scripts --prefix frontend

# Khởi động DB duy nhất và áp dụng migration.
docker compose up -d --wait db
foreach ($name in @('foundation','identity','datasets','conversation','catalog','provider_grants','chat_management','usage_review','guest_sessions','grant_limits')) {
  Get-Content "backend/migrations/$name.sql" -Raw -Encoding UTF8 | docker compose exec -T db psql -X -q -U chatsar_admin -d chatsar -v ON_ERROR_STOP=1
  if ($LASTEXITCODE -ne 0) { throw "Migration thất bại: $name" }
}

# Chỉ build khi source/dependency/Dockerfile thay đổi.
docker compose build
docker compose up -d --wait

# Oracle/permissions thật; không dùng mock thay model-live.
$env:CHATSAR_POSTGRES_TESTS = '1'
py -3.11 -m unittest discover -s evaluations/tests -v
py -3.11 -m evaluations.oracle
py -3.11 -m evaluations.semantic
py -3.11 -m evaluations.planning
py -3.11 -m evaluations.acceptance  # chỉ prepare; không gọi model
py -3.11 -m evaluations.runtime
py -3.11 -m evaluations.integration
py -3.11 -m evaluations.model_live --providers gemini --cases logistics_sum hotel_sum library_sum --prepare-only
py -3.11 -m evaluations.persistence

# Kiểm tra code trong backend: uv run --frozen ruff check app tests
# Format: uv run --frozen ruff format --check app tests
# Types: uv run --frozen mypy
# Unit: uv run --frozen pytest -q
# Frontend: npm.cmd run typecheck; npm.cmd run build (trong frontend/)
# Frontend SSR/DTO: npm.cmd test --prefix frontend (không phải browser E2E)

# Dừng đúng ChatSAR khi cần, giữ nguyên volume.
docker compose stop
```

Không chạy `down -v`, prune volumes, restart dịch vụ khác hoặc dùng rollback Git thay backup dữ liệu. Bootstrap roles chỉ chạy với volume mới; thay mật khẩu trong `.env` sau khi DB đã tạo không tự đổi mật khẩu DB. Migration dùng role admin trong DB service; API chỉ nhận app credential. Không truyền admin URL vào API container.

Các bước backup/restore đầy đủ chưa được nghiệm thu ở F1; phải bổ sung theo milestone có dữ liệu người dùng trước khi tuyên bố release an toàn. Hiện các bảng benchmark được nạp trong transaction rồi rollback; tests quyền chỉ tạo/xóa đúng bảng tổng hợp có ID ngẫu nhiên của lần chạy.

## Chat, cloud và tracing

Luồng review mới: Quản lý dữ liệu → tải file → chọn sheet → Phân tích local hoặc cấp quyền metadata cho lượt AI → xem đề xuất → Chỉnh sửa chi tiết nếu cần → cấp quyền gửi metadata/câu hỏi cho từng provider nếu muốn chat nguồn private → Xác nhận và sử dụng dữ liệu → đóng hộp thoại → chọn nguồn ở header → gửi câu hỏi. Gemini mặc định. Nguồn private vẫn private khi cấp quyền chia sẻ; quyền setup một lượt không tự cho phép gửi query tới Gemini/Knowledge. Không cần chọn synthetic cho dữ liệu thật. Nếu AI lỗi, dùng local review, kiểm ô trống/ngày/đơn vị rồi xác nhận. Không tự sửa .env.

Migration catalog là additive, không tạo bảng dữ liệu thay thế; rollback ứng dụng giữ cột mới và không DROP. Ready revision cũ vẫn đọc được với defaults, không cần reupload hoặc sửa file nguồn. Kết quả partial không dùng làm premise follow-up. Fallback cần opt-in theo request và bằng chứng Knowledge từng truy cập được; 403 gần nhất chặn fallback tự động. Timeout không tự gọi lại provider khác.

`evaluations.acceptance --live --max-requests 3 --expected-ledger 12` là lệnh của lần nghiệm thu đã được duyệt ngày 30/10: đã dùng một lượt rồi dừng vì SETUP_PROPOSAL_REJECTED. Ledger hiện 13 (Gemini 8/Knowledge 5); không chạy lại lệnh này hoặc tự dùng hai lượt còn lại sau điều kiện dừng. Dừng khi setup/provider/answer không đạt, không retry/Knowledge. Không reset ledger hoặc tăng cap 10/provider. Prepare-only có thể chạy không cần quyền generation và đối chiếu toàn bộ typed rows/checksum, sau đó dọn đúng test owner. Hạn mức .env không thay cho quyền tác vụ.

Sau Google login: tạo/chọn workspace → tải CSV/XLSX → review kiểu/NULL/timezone → xác nhận → mở bộ dữ liệu ready → chọn mô hình và gửi câu hỏi. Dữ liệu private chỉ được gửi metadata/câu hỏi tới đúng provider có quyền sharing_providers; chỉ chọn synthetic cho dữ liệu thực sự tổng hợp. Khi đổi nguồn của conversation đã có câu trả lời, tạo conversation mới. Lịch sử và kết quả được lưu trong PostgreSQL; không dùng localStorage để lưu session.

Origin browser phải trùng `APP_ORIGIN`: `localhost` và `127.0.0.1` là hai origin khác nhau. Giao diện đọc origin chuẩn từ `/api/auth/config` rồi chuyển về đó trước khi khởi tạo Google Login. Không nới allowlist/CSRF để chấp nhận tùy ý các origin. Sau đổi cấu hình local cần `docker compose up -d --wait` để container nạp lại; không build lại image chỉ vì đổi `.env`.

`evaluations.model_live --prepare-only` chỉ kiểm fidelity dữ liệu qua HTTP, không gọi model. Bỏ cờ này sẽ gọi provider thật: chỉ được chạy khi có hạn mức còn lại và quyền rõ ràng. Không chạy lệnh live để kiểm health. Mốc trước quyền bổ sung 30/10 có 12 reservations; hiện 13 sau một lượt AI Setup bị từ chối. `.env` do chủ dự án đặt max 20/budget 20 USD không cấp quyền Codex tự gọi thêm. Không xóa ledger/reset bộ đếm/tăng cấu hình để chạy thêm. Hai lượt còn lại của kế hoạch ba lượt chưa dùng do đã dừng sau FAIL. Lỗi và timeout vẫn tính reservation; số HTTP request lịch sử trước khi sửa SDK guard chưa được xác minh đầy đủ, xem PREFLIGHT.

Provider timeout hiện 60 giây; nginx proxy đọc và HTTP harness chờ 90 giây để không cắt trước provider. Mức 60 giây được đặt sau ca hotel timeout ở 30 giây, chưa xác minh live lại trong hạn mức hiện tại. Timeout không bảo đảm request phía provider đã bị hủy hoặc không bị tính phí; không tự gửi lại cùng câu hỏi khi chưa đọc lại trạng thái/lịch sử.

Langfuse dùng server hiện hữu; API container tự đổi localhost thành host.docker.internal chỉ trong bộ nhớ. Không sửa `.env`, không tạo service mới. SDK 5 dùng OTEL ingestion và Observations API v2; `/api/public/traces` cũ có thể trả 404. Chẩn đoán chỉ đọc field metadata do ChatSAR đặt, không in metadata SDK toàn bộ vì có thể chứa public key. `artifacts/model-live.json` và `artifacts/langfuse-proof.json` là bằng chứng local bị Git bỏ qua; báo cáo public chỉ ghi metrics và dữ liệu tổng hợp đã duyệt.
