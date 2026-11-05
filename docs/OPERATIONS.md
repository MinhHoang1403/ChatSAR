# Vận hành ChatSAR

## Kiểm kê và đồng bộ 05/11/2026 — không triển khai Giai đoạn 2

Source backend19module + requirements.lock và frontend HTML/JS/CSS build local
đã đối chiếu byte với runtime. Image API
`sha256:a64386015a2824bd640d2bbfadf3f2b5602e5ffcace7cf9450c407c5cc2cf058`, web
`sha256:07a8e6baa4a0a5f2e27e4209fa0df6e2751d3d3d60fc7471b3469c52e8387ada`; DB
giữ digest pin trong compose. Không đổi Dockerfiles/dependencies nên không
rebuild image; CI exact commit vẫn kiểm Docker build. Local restartapi/web đã
kiểm, không restartDB hoặc dịch vụ khác.

Trong phiên kiểm kê, owner xác nhận tự cập nhật `GEMINI_API_KEY` trong `.env`;
đây là thay đổi hợp lệ của owner, Codex không khôi phục/ghi đè khóa. Kiểm drift
chỉ hiển thị tên biến, không giá trị; chỉ API cần nạp lại cấu hình. Dùng
`docker compose -p chatsar up -d --no-build --no-deps --wait api` sau kiểm không
có thao tác pending để recreate đúng API bằng image cũ, giữ uploads/database và
không gọi model. Không dùng rebuild hoặc sửa quota để thử key; key được nạp
không chứng minh provider live đã được kiểm.

Snapshot trước/sau phải so hash toàn
rows25bảngapp/data,10migrations,14originalfiles và appsource;
ledger568/grants/reviews giữ nguyên. `.env` hash khác snapshot đầu do owner đổi
khóa, so cuối với bản owner vừa cập nhật; không công khai hash secret/config
hoặc raw data. Evidence local tại `artifacts/cleanup-2026-11-05/`, Git bỏ qua;
kết quả/giới hạn tại đầuPREFLIGHT.

Docker inventory không có image ChatSAR cũ/dangling đủ điều kiện xóa;
chỉ2appimages đang dùng. Giữ `chatsar_database`, `chatsar_uploads`,
`chatsar_default`, image rollback/current và toàn resources dự án khác. Build
cache38.62GB là cache dùng chung, không có bằng chứng layer ownership đủ để dọn
riêng ChatSAR nên giữ REVIEW. Không chạy prune.

12đường dẫn cache/build có thể tái tạo đã kiểm root/reparse point và kiểm
kê84files/66,069,038bytes, nhưng lệnh xóa bị cơ chế xét duyệt tự động từ chối
(`blocked by policy`), kể cả danh sách LiteralPath cố định. **Chưa xóa, giải
phóng0byte**; không thay công cụ để lách chặn. Không coi cleanup cache đã PASS.
Source/tests/migrations/oracle và artifacts nghiệm thu được giữ vì còn
dependency/audit value. Kế hoạch Giai đoạn2 ở Implementation Plan§17 là
**PLANNED / PENDING OWNER APPROVAL**, chưa coding/cloud mới;36Gemini manual
không được dùng.

## Khôi phục môi trường phát triển Windows và VS Code — 02/11/2026

Nếu Python gốc trong `%AppData%` bị xóa, `.venv` có thể vẫn tồn tại nhưng không
chạy được. Dùng Python 3.11 còn hợp lệ và đồng bộ đúng file khóa, không nâng
dependency hoặc tạo môi trường thứ hai:

```powershell
uv sync --project backend --frozen --python 3.11
npm ci --ignore-scripts --prefix frontend # Chỉ khi node_modules thiếu hoặc hỏng
```

Mở thư mục gốc `ChatSAR` trong VS Code. `.vscode/settings.json` giới hạn tìm
venv vào `backend/.venv` và khai báo project dùng venv;
`.vscode/extensions.json` đề xuất các extension Python/Pylance/Python
Environments/Ruff/Mypy. Không đặt `python.defaultInterpreterPath` chứa
`${workspaceFolder}`: Python Environments 1.20.1 trong Antigravity còn dùng
nguyên chuỗi này khi dò interpreter toàn cục, gây cảnh báo dù venv hợp lệ. Cấu
hình cá nhân VS Code ngoài Git dùng
`python-envs.terminal.autoActivationType = command` và theme `Light Modern`.
Chọn môi trường `chatsar-backend` nếu VS Code đã lưu lựa chọn cũ; mở terminal
mới sau khi thay môi trường. Kiểm nhanh
`python -c "import sys; print(sys.executable)"` phải trỏ tới
`backend\.venv\Scripts\python.exe`. Theo
[tài liệu chính thức](https://code.visualstudio.com/docs/python/environments),
chế độ command tự chạy lệnh kích hoạt khi mở terminal, không phụ thuộc
PowerShell profile đã mất. Không đưa secrets từ `.env` vào terminal hoặc thay
chính sách hệ thống.

Khôi phục 02/11: tạo lại cùng `backend/.venv` bằng Python 3.11.9 còn trên máy,
đủ 65 gói đúng uv.lock. Đã tải lại Python 3.11.9 do uv quản lý và sửa launcher
`python`/`python3`; chỉ đổi tên launcher Python3.12 đã hỏng thành
`.exe.disabled` để có thể khôi phục, không xóa interpreter đang hoạt động.
GitHub CLI được phục hồi metadata tài khoản và dùng lại credential còn trong
Windows keyring, không cấp thêm quyền. Node24.19.0/npm11.17.0 và frontend
dependencies còn đủ, typecheck/build đạt. Mypy/Ruff từng nhận nhầm đường dẫn thư
mục làm executable gây spawn ENOENT; đã sửa đường dẫn rõ ràng, Mypy dùng đúng
gói khóa và cwd backend. Log xác nhận Mypy1.20.2/Ruff0.17.3/Pylance hoạt động;
terminal mới tự kích hoạt venv. Kiểm pip dependency compatibility, Mypy19module
và Ruff đều đạt.

Container ChatSAR trước đó đã dừng; `docker compose up -d --no-build --wait` đưa
đúng web/api/db lên healthy với volumes cũ. Readiness/migrations/source
bytes/lịch sử/ledger568(grant464) giữ nguyên; không gọi provider hoặc đổi
keys/flags/quota. Không tải lại Docker/model weights/extension còn nguyên. Theme
là lựa chọn cá nhân, không ép vào repo.

## Khôi phục Antigravity — 04/11/2026

Cấu hình cá nhân ở `%AppData%/Antigravity IDE/User/settings.json`, độc lập với
VS Code. Theme có ID `Default Light Modern` trên bản Antigravity này. Python mặc
định toàn máy dùng interpreter còn hợp lệ; project ChatSAR tự chọn venv 3.11.9
qua `pythonProjects` và `workspaceSearchPaths`. Giữ Python Environments hoạt
động để Mypy/Ruff/Pyrefly nhận interpreter, nhưng đặt riêng Antigravity
`python-envs.terminal.autoActivationType = off`. Profile terminal mặc định
`PowerShell (ChatSAR)` chạy `backend/.venv/Scripts/Activate.ps1` khi thư mục
hiện tại thuộc ChatSAR; ngoài dự án không kích hoạt venv. Cách này tránh API
terminal chưa tương thích và lệnh kích hoạt lặp bị timeout, không sửa chính sách
PowerShell hoặc file cài đặt IDE. Terminal đã mở giữ trạng thái cũ; tạo terminal
mới để nhận cấu hình.

Các gói extension chính thức đã khôi phục: Python 2026.4.0 có PET cho Windows,
Python Environments 1.20.1 và Mypy 2026.6.0 có đủ thư viện đi kèm. GitHub Pull
Requests dùng bản 0.112.0 tương thích IDE 1.107, tránh API chat của bản 0.126.0;
bản cài từ VSIX được ghim, không sửa manifest hoặc bật API thử nghiệm. Các
extension còn lại được kiểm tra cùng dependency tích hợp sẵn, không cần cài lại
khi còn đủ. Sửa khoảng trắng dòng phân cách bảng trong CONTRACTS để hết sáu cảnh
báo MD060; giữ bộ kiểm tra Markdown hoạt động và chọn formatter mặc định rõ
ràng.

Đã kiểm lại 65 package backend đúng file khóa, dependency compatibility, 19
module Mypy, Ruff, frontend typecheck/build và readiness Docker; không gọi
model. Bản phục hồi cấu hình cá nhân và danh sách extension nằm ngoài AppData
tại `%UserProfile%/.antigravity-ide/settings-recovery.json`, không chứa
credential. Không còn bản sao cài đặt cá nhân trước lần xóa AppData để khẳng
định khôi phục giống từng tùy chọn cũ; bản phục hồi mới lưu cấu hình đang dùng
đã kiểm tra.

## Bàn giao vận hành 01/11/2026 — ngừng gọi model, còn36manual

Nguồn ứng dụng19module fb50d49 không thay; web/api/db healthy sau fullrestart.
Ledger568(Gemini563/Knowledge5), grant464used, reserve6.8002886USD,
knownestimate0.7158162USD. Sáu unknowncost vẫnNULL/fullreserve, đềuđãreview
fullsnapshot; khôngunreviewedunknown/duplicate dispatch. Cùnggrant max495→500
chỉ sau toàn bộCodexcalls dừng; budget10/baseline/ledger/envkeysflags giữ,
before/afterhashkhớp. Còn36lượt dànhowner, không tựgọi thêm để hoàn tất mẫu số
benchmark đã giảm.

UIGoogle sau reload đọc lại COUNT4/SQL; các
source0.35/0.40/context0.47→0.43→0.26 exactsnapshotgiữ.
Original199/full127ledgerrows/2Google/privateB/history0.30/11goldplansnguyênvẹn.
Cleanup chỉ UUIDtestworkspace52messages đãsnapshot và khôngpending; không
nguồnGoogle/ledger. NTPstripchart hiệnlệch~0.33s, TimeService vẫnunsync
vàresyncOSAccessDeniedlàlịchsử; không đổiGoogleverification.

Trạngthái/điểm/phạmvi chưađo xemđầuPREFLIGHT; không dùng các checkpoint BLOCKED
phía dưới làm current. Từ nay kiểm thêm chỉ khi cóthayđổithật/lỗimới hoặcowner
yêu cầu; ưu tiên câu tựnhiên theo ý định, không yêu cầu người dùng đọc tênfield.
PR1vẫnDraft, chưamerge/Phase2.

## Quyền hiện hành: tối đa 8 review, giữ nguyên 500/10 — 01/11/2026

Owner đã duyệt bổ sung3 review (tổng8): đúng
b66d8f40-6557-4570-9d87-22de67f5fd21 và tối đa2 phản hồi429/503 đã xác minh
khác. CLI `--review-limit 8` là lựa chọn có chủ đích ngoài API, default3 và chỉ
cho grant >400 requests; trần request500, Codex495 và budget10USD không đổi.
Review thứ6 đã apply, fullrow/UNKNOWN/fullreserve/count giữ nguyên, 2 review còn
lại chưa dùng. Mỗi lỗi mới vẫn dừng nhóm kiểm thử để đối chiếu bằng chứng và
cooldown; không auto-review/auto-retry, không chấp nhận
transport/timeout/HTTPkhác chỉ vì còn quyền review. Không vượt8 hoặc giảm
reserve/cost bằng suy đoán.

## 01/11/2026 — Pending503, không tự vượt5review

Currentgrant69d37b9b-fd6d-4296-9189-9fb5303b46a1,max495Codex/budget10USD
(ownertổng500,giữ5manual).
Ledger503,grant399/reserve5.8080951USD,UNKNOWN6/reviewed5.
b66d8f40-6557-4570-9d87-22de67f5fd21
làdirect503/dispatch1/PROVIDER_TEMPORARY/reserve0.0152458,usagecostNULL;CLIpreviewđãsẵn,applychưađượcduyệtvìtrần5đãdùnghết.
Khôngđổicost0,xóalượt,resetledger/grant/keys,bậtSDKretryhoặcgọigenerationkhácđểnéguard.
RestartgiữUNKNOWN/fullsnapshot/reservevàchặnvẫnhiệulực.

ChỉkhiownerduyệtbổsungcụthểmớiđượcmởCLIreviewlimit/applytrongđúngscope.
Giữfullsnapshot/numericreserve/NULLcost/count,cooldown60/300s,operatorCLIngoàiAPI,APPchỉSELECTreviews.
Khigenerationcóthểtiếptục,ưu
tiên78NLgốc+12systemguardvàbộheldout2schema;budgettínhcảretry/seed/HTTPerrors,chừa5manual.
Khôngtựhạtiêuchíhaygộpsourcecũ. Thực
tếstatusxemPREFLIGHTđầu,tránhdùngcheckpointlịchsửlàđiểmcuối.

## Đối soát429 có quyền riêng —31/10/2026

Owner đã duyệt đúng HTTP429 8e3bf1d7-dcf8-47de-9710-716907b2c309. CLI
usage_review nhận --http-status429 (mặc định503); so
fullsnapshot/grant/model/status/dispatch1/HTTP direct/error tương ứng/all
tokens-costNULL/reserve dương. Mặc định preview, --apply chỉ admin và cần quyền
cụ thể từng request. Giữ cả count và fullreserve; không sửa ledger hoặc biến
UNKNOWN thành0. Tối đa3review429/503 tổng mỗi grant. API chỉ SELECT audit hợp
lệ, vẫn cooldown60s, unknown khác/mismatch vẫn chặn. Không tự approve hoặc
retry. Một probe sau audit đã200, rồi2ca MIN/status qua HTTP đạt. Chưa biết429
vừa rồi làRPM/TPM/RPD; không suy từ recovery thànhquota vô hạn. Giãn các lượt
harness15s, không gọi song song hoặc thử khiusage chưa rõ. Tài liệu:
<https://ai.google.dev/gemini-api/docs/rate-limits> và
<https://ai.google.dev/gemini-api/docs/troubleshooting> .

## Quota đã áp dụng và luồng kiểm tiếp — 31/10/2026

Đã áp dụng grant_limits sau guest_sessions (10migrations). Chỉ thay hai CHECK
của provider_grants, không sửa usage/baseline.
Grant69d37b9b-fd6d-4296-9189-9fb5303b46a1 thực tế495requests/10USD, giữ5manual
trong tổng500; .env global604/Gemini599/Knowledge5,
flags/keys/globalbudget20khôngđổi. Không chạy authorize tạo grant khác hoặc
reset ledger. Migration chạy lặp an toàn và không tự tăng quota; app vẫn chỉ
SELECT grant/review. Evidence mở quota giữ snapshot199rows.

Đơn vị model gợi ý không tự áp dụng khi owner lưu before/after; owner nhập đúng
unit ở chi tiết nếu cần. Xem header so sánh để kiểm units đã nhập. Cached
proposal vẫn reuse0call, không dùng cache để vượt policy unit mới hoặc source
binding. Kiểm live theo batch, giữFAIL/refusal và source fingerprint; không gộp
source khác nhau thành accuracy. Không merge hoặc Phase2.

## Luồng dữ liệu mới và quyền500 — 31/10/2026

Chọn file tự chuẩn bị, xem trước/sau rồiLưu; không còn bấm phân tích/cấp quyền
riêng. Cachedsetup tự mở, XLSX nhiều sheet chọn đúng trang. API
normalization-preview dùng cùng validator với publish/toàn bảng, không
callmodel. LỗiAI sẽ nói rõ dùng nhận diện từ file; không tự retry để tiêu
credits. Nguồn mới được cấu hình cho2model theo policy owner, actualdispatch vẫn
chọn một model/guard/cap; privategiữnguyên.

Owner vừa cấp trầntổng500requests/10USD dự phòng, giữ5manual. Một
grant69d37b9b-fd6d-4296-9189-9fb5303b46a1 và ledger199/95used tại checkpointUI,
không reset/newgrant/đổi keys. Chỉ tăngcap sau migration và audit snapshot đúng
quyền mới; Knowledgecap5đãdùng5, Llama/BGEkhôngthêm. Các đoạn100/1.50 phía dưới
là lịch sử, không phải ngân sách hiện hành sau áp dụng mở rộng.

## Vận hành audit503 — 31/10/2026

Không sửa usage/cost thành0, không đổi grant/reset ledger.

```powershell
python -m operations.usage_review --usage-id UUID --grant-id UUID --model gemini-3.5-flash-lite --reserve DECIMAL --authority "Quyền cụ thể của chủ dự án"
```

Lệnh chỉ preview. Sau kiểm đúng evidence/quyền, thêm `--apply` để ghi audit bằng
chatsar_admin qua Compose db. API không nhận mật khẩu admin, không tự chạy công
cụ này. Công cụ chỉ nhận verified HTTP503/error/dispatch1/UNKNOWN/fullreserve và
snapshot nguyên vẹn, giới hạn3review503/grant; không phải bypass chung. Review
trùng/mismatch/hết budget phải điều tra, không sửa trực tiếp bảng để vượt.

Lần gửi có chủ đích sau lỗi cần key mới, đợi cooldown60s (hai503liền300s). Không
retry cùng key/pending; GET history trước khi quyết định gửi lại.
Timeout/network/unknown thiếu response vẫn giữ gate. Không kết luận Google không
thu phí; reserve tiếp tục tính đầy đủ. Lượt503lịch sử đã được chủ dự án cho phép
audit, các phần dưới giữ lịch sử trước quyền31/10; xem đầuPREFLIGHT về số liệu
hiện hành.

## Vận hành hiện hành sau đợt sửa — 30/10/2026

Live đang dừngUSAGE_UNKNOWN doHTTP503 mới a4755acf-0039-4928-890e-0f57b6b4322d,
khôngphảilỗiconfigsource. Khônggọihealthmodel/retry/chuyểngrant hoặc
thêmreviewHTTP400cho503. Giữtokens/costNULLvàreserve0.0141532USD. Quyềnmới
thêm100calls/1.50USD,grant
riêng69d37b9b-fd6d-4296-9189-9fb5303b46a1,max95Codex;đãdùng23,reserve0.3117407USD.
Ledger127=122/5. Còn77mới và9cũmanual nhưng usagegate vẫn dừng; .env chỉđổi
total/provider cap vàactivegranttheoquyềnmới,keys/flags/budgetglobalgiữnguyên.
Không dùngquota còn đểtựbỏchặn.

AI Setup có thêmcheckbox gửi tốiđa20giátrịphânbiệt/cột để đềxuất cáchgọi;
mặcđịnhtắt, cầnmetadataopt-in,khônggửidòng.
Chủnguồnreview/confirmmappingtrướcpublish,quyềnhỏiGemini riêng. Không sửa
nguồnGoogle thật đểbenchmark; bảngquality-ui.csv tổnghợp2rowsởkhônggian
nghiệmthu củaaccountBgiữprivate/sharing[]. AccountA/historySQLgiữnguyên.
BrowserhaiGoogleđãuserloginvàkiểm chuyểnidentity;chưaphải
haiindependentprofilesđồngthời.

157unit/42integration/28evaluation/14frontend+types/build đãkiểm.
Chạyquota/integration/acceptance tuần tự vìfixturesquotacórows
tạmtácđộnggloballedgerassertion. Hai plan/goldgiữnguyên. Phase1NOT_ACCEPTED;
xemđầuPREFLIGHT.

## Bổ sung hiện hành: phiên khách — 30/10/2026

Áp dụng migration guest_sessions sau usage_review trước build/start; readiness
yêu cầu đủ9migrations. Trang chủ không còn yêu cầu login trước. Đăng xuất chỉ
thu hồi session tài khoản, không xóa dữ liệu Google. Login từ khách mở dữ liệu
tài khoản, không nhập guest. Guest token không được lưu bền phía trình duyệt;
refresh tạo phiên sạch. Frontend pagehide/login gửi DELETE keepalive; server
giới hạn token2giờ và reaper60giây dọn guest hết phiên, không chạm provider
ledger hoặc Google. Pending setup/ingestion/model trì hoãn cleanup đến khi
xong/recovery, không hủy hoặc replay HTTP đang bay. Nếu trình duyệt không gửi
cleanup, dữ liệu tạm còn server đến TTL/reaper; không coi việc UI mất dữ liệu là
chứng minh xóa vật lý ngay mọi tình huống.

Kiểm guest dùng mock provider, quota thực không tăng.9lượt còn lại dành chủ dự
án, không gọi để smoke test guest. Khách vẫn phải cấp quyền hỏi đáp cho nguồn
private và chịu cùng budget/provider guards. Không có public deployment hoặc
quota vô hạn mới.40integration gồm6guest;14frontend,148unit/types/build PASS.
Tổng Phase1 vẫn NOT_ACCEPTED.

**Hiện hành 30/10/2026:** Phase1 NOT_ACCEPTED. QueryRequest đã vào một runtime
sau canary/so sánh/printing;4FAIL mở rộng còn giữ. Usage review admin theo từng
usage_id giữ toàn reserve cho HTTP400 lịch sử, không sửa tokens/costNULL.
Unknown mới vẫn chặn; app không tự approve. .env/keys/flags không đổi. Migration
usage_review additive, app chỉ đọc provider_usage_reviews; không cấp
INSERT/UPDATE/DELETE cho app/reader. Không tự thêm review vì chỉ thấyHTTP400:
phải có chứng cứ/snapshot/quyền chủ dự án. Đây là dự phòng được chấp thuận,
không là hóa đơn.

Đợt này41Gemini, tổng grant91/100, reserved1.2290194/1.50USD. Codex dừng
generation tại91/95. Còn9lượt tổng, ít nhất5dành chủ dự án; đã chuyển cap
grant95→100 khi bàn giao toàn9lượt cho chủ dự án trong đúng quyền100đã cấp;
budget1.50USD/baseline/ledger giữ nguyên, Codex không gọi thêm sau bàn giao.
Không dùng9lượt đó làm quyền tự test ở nhiệm vụ sau.
Ledger104=Gemini99/Knowledge5; Knowledge/LlamaParse/BGE mới0.

Nguồn ready: Data Manager → chọn đúng file → Quyền hỏi đáp với mô hình → chỉ
đánh dấu provider muốn cấp → Lưu quyền hỏi đáp; bỏ dấu và lưu để thu hồi cho
lượt sau. Private giữ private. AI Setup consent không tự cấp query. Pending thì
đợi hoàn tất trước đổi quyền. Nguồn synthetic vẫn theo chính sách kiểm thử đã
xác nhận. Workbook-ui.xlsx kiểm thử đã trở lại sharing[]; chat Nghiệm thu quyền
và SQL — 30-10 giữ result0.3và SQL thật sau restart, xem history không gọi
model.

**Các mục bên dưới là lịch sử vận hành trước cập nhật này.** Dùng báo cáo đầu
PREFLIGHT và CONTRACTS cho gate/usage hiện hành.

## Vận hành nền tảng ChatSAR — lịch sử

## Natural Answers/SQL evidence — 30/10/2026

Không migration mới, giữ7 migration/volumes hiện hữu. API lưu processing
additive trong envelope: SQL placeholders/tên bind, không raw values; source
snapshot, actual provider, durations và failed_stage. Owner kiểm ở
conversation/result, không thêm API SQL tự do. Panel chỉ đọc history, không
generate/compile/execute. Legacy thiếu SQL không backfill từ plan. Checkpoint
trước execute có thể còn pending khi crash/final persist lỗi; recovery giữ SQL
và chuyển in_progress→unknown, không replay. Không đổi unknown thành succeeded
vì chỉ đọc thấy statement.

Composer tất định không thêm model calls. Live vẫn
USAGE_UNKNOWN/ledger63=58Gemini+5Knowledge, không gọi để kiểm health/UI; quota
còn không cấp quyền bypass. Runtime143unit/33integration/12frontend PASS, SQL
provenance/persistence qua restart có provider mock trong process harness, không
model E2E. Fresh Google/two-account/positive model SQL browser chưa nghiệm thu.
Ảnh/evidence local ở artifacts, không đưa lên public. Trạng thái hiện hành và
checklist đầu PREFLIGHT; các phần dưới là lịch sử vận hành.

## Bổ sung quản lý chat/hồ sơ 30/10/2026

Migration `chat_management` chạy sau provider_grants: thêm phone/interests và
conversation.revision_id, backfill chỉ lịch sử có một revision. Không DROP hay
thay bảng vật lý; rollback code giữ cột mới. API xóa chỉ chat/messages/results
trong workspace được chọn, giữ nguồn/workspace/ledger. Chặn pending tại server;
không dùng delete trên lịch sử thật để nghiệm thu. Hồ sơ chỉ principal hiện tại,
không thay Google và không đưa vào prompt/trace. Composer dấu+ mở upload/tạo
workspace/quản lý dữ liệu; model mặc định Gemini, Knowledge chọn tay, fallback
UI đã bỏ. Không tự gọi model để kiểm giao diện khi USAGE_UNKNOWN.

## Trạng thái vận hành sau ổn định 30/10/2026

Runtime healthy, Phase1 NOT_ACCEPTED do chất lượng model còn thiếu, model-live
BLOCKED_USAGE_UNKNOWN sau một HTTP400 không usage. Không gửi thêm model request
để test health, không reset hoặc sửa usage/dispatch counter. Các đoạn quota cũ
bên dưới là lịch sử; quyền mới tối đa100Gemini/1.50USD, Codex95, Knowledge mới0.
Đã dùng50, còn trần45Codex/50tổng nhưng guard dừng live. .env giữ
keys/flags/global budget20; globalcap113, Geminicap108, Knowledgecap5, active
grant cap95/1.50USD. Giá trị trước thay đổi nằm trong
artifacts/stabilization-quota.json; không coi global budget20 là quyền bổ sung.

Grant chỉ admin cấp, app chỉ đọc; migrations hiện gồm
foundation/identity/datasets/conversation/catalog/provider_grants. Migration mới
additive, rollback app giữ cột/bảng quota; không DROP hoặc sửa ledger. Default
runtime vẫn cloudOFF/max0/budget0 và providercap10. Cần đối chiếu usage/billing
lượt d10d5f23-d15d-4c9e-8e21-37e67b510b1c trước khi xem xét quyền tiếp tục;
thiếu usage không phải chi phí0. Không tự bỏ guard vì còn quota.

Workspace nghiệm thu trên tài khoản hiện hữu giữ 3 file synthetic để chủ dự án
xem: hotel-ui.csv ready, workbook-ui.xlsx(Data) ready/private không cloud,
fallback-ui.csv needs_review/local. History “Tổng tiền phòng?” đọc lại300.15
không gọi model. Browser đã logout và reset viewport. Có thể kiểm login hai tài
khoản/upload/local review độc lập trong khi live bị chặn. Không dùng test
harness cleanup workspace Google thật này; harness chỉ dọn đúng UUID test owners
do nó tạo.

Chỉ chạy tại root repository chính. Một Compose project `chatsar`, volume
`chatsar_database`, không có test/staging project thứ hai. DB không publish port
ra host. Web `http://localhost:18181`; API health
`http://127.0.0.1:18081/health`. Kiểm tra lại port trước mỗi lần khởi động nếu
môi trường đã thay đổi.

## Cấu hình local

`.env.example` chỉ chứa placeholder và provider OFF/budget 0. `.env` local bị
Git bỏ qua. Mật khẩu DB/session phải ngẫu nhiên riêng cho ChatSAR. Không in
`docker compose config` đầy đủ vì có thể lộ secrets; dùng
`docker compose config --quiet` để kiểm tra cấu hình.

Chủ dự án có thể điền `GOOGLE_CLIENT_ID`, `KNOWLEDGE_BASE_URL`, các biến
`LANGFUSE_*` vào `.env`, không gửi secrets qua chat. Google Web Client mới cần
origin `http://localhost:18181`; cấu hình production HTTPS riêng sẽ được chốt
sau. Không sửa OAuth client ShopQuery. Giữ nguyên flags enabled do người dùng
đặt; mỗi tác vụ phải kiểm tra quyền và hạn mức riêng. Smoke tests
Gemini/Knowledge tối đa 10 calls/provider hoặc giới hạn thấp hơn trong cấu hình.
LlamaParse enabled không cấp quyền parse ở Phase 1. Không ghi đè .env.

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

Không chạy `down -v`, prune volumes, restart dịch vụ khác hoặc dùng rollback Git
thay backup dữ liệu. Bootstrap roles chỉ chạy với volume mới; thay mật khẩu
trong `.env` sau khi DB đã tạo không tự đổi mật khẩu DB. Migration dùng role
admin trong DB service; API chỉ nhận app credential. Không truyền admin URL vào
API container.

Các bước backup/restore đầy đủ chưa được nghiệm thu ở F1; phải bổ sung theo
milestone có dữ liệu người dùng trước khi tuyên bố release an toàn. Hiện các
bảng benchmark được nạp trong transaction rồi rollback; tests quyền chỉ tạo/xóa
đúng bảng tổng hợp có ID ngẫu nhiên của lần chạy.

## Chat, cloud và tracing

Luồng review mới: Quản lý dữ liệu → tải file → chọn sheet → Phân tích local hoặc
cấp quyền metadata cho lượt AI → xem đề xuất → Chỉnh sửa chi tiết nếu cần → cấp
quyền gửi metadata/câu hỏi cho từng provider nếu muốn chat nguồn private → Xác
nhận và sử dụng dữ liệu → đóng hộp thoại → chọn nguồn ở header → gửi câu hỏi.
Gemini mặc định. Nguồn private vẫn private khi cấp quyền chia sẻ; quyền setup
một lượt không tự cho phép gửi query tới Gemini/Knowledge. Không cần chọn
synthetic cho dữ liệu thật. Nếu AI lỗi, dùng local review, kiểm ô trống/ngày/đơn
vị rồi xác nhận. Không tự sửa .env.

Migration catalog là additive, không tạo bảng dữ liệu thay thế; rollback ứng
dụng giữ cột mới và không DROP. Ready revision cũ vẫn đọc được với defaults,
không cần reupload hoặc sửa file nguồn. Kết quả partial không dùng làm premise
follow-up. Fallback cần opt-in theo request và bằng chứng Knowledge từng truy
cập được; 403 gần nhất chặn fallback tự động. Timeout không tự gọi lại provider
khác.

`evaluations.acceptance --live --max-requests 3 --expected-ledger 12` là lệnh
của lần nghiệm thu đã được duyệt ngày 30/10: đã dùng một lượt rồi dừng vì
SETUP_PROPOSAL_REJECTED. Ledger hiện 13 (Gemini 8/Knowledge 5); không chạy lại
lệnh này hoặc tự dùng hai lượt còn lại sau điều kiện dừng. Dừng khi
setup/provider/answer không đạt, không retry/Knowledge. Không reset ledger hoặc
tăng cap 10/provider. Prepare-only có thể chạy không cần quyền generation và đối
chiếu toàn bộ typed rows/checksum, sau đó dọn đúng test owner. Hạn mức .env
không thay cho quyền tác vụ.

Sau Google login: tạo/chọn workspace → tải CSV/XLSX → review kiểu/NULL/timezone
→ xác nhận → mở bộ dữ liệu ready → chọn mô hình và gửi câu hỏi. Dữ liệu private
chỉ được gửi metadata/câu hỏi tới đúng provider có quyền sharing_providers; chỉ
chọn synthetic cho dữ liệu thực sự tổng hợp. Khi đổi nguồn của conversation đã
có câu trả lời, tạo conversation mới. Lịch sử và kết quả được lưu trong
PostgreSQL; không dùng localStorage để lưu session.

Origin browser phải trùng `APP_ORIGIN`: `localhost` và `127.0.0.1` là hai origin
khác nhau. Giao diện đọc origin chuẩn từ `/api/auth/config` rồi chuyển về đó
trước khi khởi tạo Google Login. Không nới allowlist/CSRF để chấp nhận tùy ý các
origin. Sau đổi cấu hình local cần `docker compose up -d --wait` để container
nạp lại; không build lại image chỉ vì đổi `.env`.

`evaluations.model_live --prepare-only` chỉ kiểm fidelity dữ liệu qua HTTP,
không gọi model. Bỏ cờ này sẽ gọi provider thật: chỉ được chạy khi có hạn mức
còn lại và quyền rõ ràng. Không chạy lệnh live để kiểm health. Mốc trước quyền
bổ sung 30/10 có 12 reservations; hiện 13 sau một lượt AI Setup bị từ chối.
`.env` do chủ dự án đặt max 20/budget 20 USD không cấp quyền Codex tự gọi thêm.
Không xóa ledger/reset bộ đếm/tăng cấu hình để chạy thêm. Hai lượt còn lại của
kế hoạch ba lượt chưa dùng do đã dừng sau FAIL. Lỗi và timeout vẫn tính
reservation; số HTTP request lịch sử trước khi sửa SDK guard chưa được xác minh
đầy đủ, xem PREFLIGHT.

Provider timeout hiện 60 giây; nginx proxy đọc và HTTP harness chờ 90 giây để
không cắt trước provider. Mức 60 giây được đặt sau ca hotel timeout ở 30 giây,
chưa xác minh live lại trong hạn mức hiện tại. Timeout không bảo đảm request
phía provider đã bị hủy hoặc không bị tính phí; không tự gửi lại cùng câu hỏi
khi chưa đọc lại trạng thái/lịch sử.

Langfuse dùng server hiện hữu; API container tự đổi localhost thành
host.docker.internal chỉ trong bộ nhớ. Không sửa `.env`, không tạo service mới.
SDK 5 dùng OTEL ingestion và Observations API v2; `/api/public/traces` cũ có thể
trả 404. Chẩn đoán chỉ đọc field metadata do ChatSAR đặt, không in metadata SDK
toàn bộ vì có thể chứa public key. `artifacts/model-live.json` và
`artifacts/langfuse-proof.json` là bằng chứng local bị Git bỏ qua; báo cáo
public chỉ ghi metrics và dữ liệu tổng hợp đã duyệt.
