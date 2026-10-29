# ChatSAR — Quy tắc phát triển và quản lý repository

Áp dụng cho toàn bộ dự án tại `C:\Work\ChatSAR`, trong mọi phiên Codex. Đây là nguồn quy tắc chính; `AGENTS.md` chỉ dẫn đến file này, không nhân bản toàn bộ nội dung.

**Trạng thái hiện tại:** Chủ dự án đã cho phép kiểm tra tiền triển khai và Giai đoạn 1 (F1 → F4) ngày 29/10/2026, theo kế hoạch và nghiệm thu từng mốc. Giữ Giai đoạn 1 trên feature branch đến khi được duyệt merge. Điều kiện bên ngoài thiếu phải ghi BLOCKED và chỉ tiếp tục phần độc lập an toàn; xem `docs/DECISIONS.md`, `docs/PREFLIGHT.md`. Được smoke test tối đa 10 calls Gemini và 10 Knowledge, hoặc hạn mức cấu hình thấp hơn; không sửa .env/flags enabled, không gọi LlamaParse trong Phase 1. Được tiếp tục F3/F4 qua test harness an toàn khi Google live BLOCKED; không tự sang Giai đoạn 2 hoặc tác động dự án khác.

**Tài liệu thực tế trong repository:** [Implementation Plan](../docs/IMPLIMENT_PLAN.md) và [Master Plan](../docs/ChatSAR_MASTER_PLAN.md). Giữ nguyên tên file hiện có; các tên kế hoạch cũ được nhắc trong nội dung không phải yêu cầu tạo bản sao. Trước lần sửa mã nguồn đầu tiên, đọc toàn bộ Implementation Plan theo mục 0.1 của tài liệu; các nhiệm vụ sau đọc lại phần liên quan.

**Cách kiểm chứng:** Xác định điều kiện nghiệm thu trước khi thay đổi; kiểm tra nội dung/diff, chạy phép thử phù hợp và báo bằng chứng thực tế. Dùng `PASS` khi đã kiểm tra đạt, `FAIL` khi đã kiểm tra không đạt, `BLOCKED` khi thiếu điều kiện/quyền, `NOT_RUN` khi chưa chạy. Không suy diễn kết quả của một tầng kiểm thử sang tầng khác.

## RULE 01 — Code sạch, rõ ràng và dễ bảo trì

Bắt buộc:

- Code sạch, có cấu trúc và dễ đọc.
- Đặt tên biến, hàm, class, module và file đúng chức năng.
- Không đặt tên mơ hồ như `temp`, `misc`, `new_logic`, `final_fix`.
- Mỗi module có một trách nhiệm rõ ràng.
- Dùng type hints và validation phù hợp.
- Tách nghiệp vụ khỏi API, giao diện và kết nối dịch vụ bên ngoài khi có nhu cầu thực tế.
- Không nhân bản logic hoặc triển khai nhiều cách xử lý cùng một chức năng.
- Comment bằng tiếng Việt, giải thích nghiệp vụ, logic khó, điều kiện, công thức và lý do xử lý.
- Comment phải giúp người đọc hiểu code nhưng không lặp lại những gì dòng code đã thể hiện rõ.
- Không viết comment thừa chỉ để tăng số lượng.
- Khi sửa code, ưu tiên giải pháp đúng nguyên nhân gốc, không vá từng câu hỏi hoặc từng trường hợp riêng lẻ.

**Mục tiêu:** Người khác đọc code có thể hiểu chức năng và dễ dàng sửa đổi, bảo trì.

## RULE 02 — Không sử dụng tên giai đoạn trong production code

Không sử dụng các nhãn quản lý kế hoạch để đặt tên:

- Source files.
- Classes/functions/variables.
- Database tables.
- API endpoints.
- Docker services/images do dự án tự đặt tên.
- Runtime modules hoặc business logic.

Các nhãn cần tránh gồm:

`v1`, `v2`, `s1`, `s2`, `e3`, `freeze`, `frozen`, `phase1`, `stage2`, `final_fix`, `new_version` và những cách đặt tên tương tự.

Chỉ sử dụng chúng khi thật sự cần trong tài liệu kế hoạch, milestone hoặc lịch sử phát triển.

**Ngoại lệ:** Không thay đổi model ID, phiên bản thư viện, API version, tên tiêu chuẩn hoặc tên công nghệ chính thức của bên thứ ba, chẳng hạn `bge-reranker-v2-m3`, chỉ để né quy tắc đặt tên.

Tên code phải thể hiện chức năng thực tế, không thể hiện thời điểm hoặc giai đoạn được tạo ra.

## RULE 03 — Mọi phương pháp và công nghệ phải có căn cứ

Khi lựa chọn kiến trúc, thuật toán, phương pháp, công thức hoặc công nghệ:

1. Ưu tiên tài liệu kỹ thuật chính thức.
2. Tham khảo bài báo khoa học, nghiên cứu được công bố, benchmark hoặc tài liệu học thuật phù hợp.
3. Phân biệt thông tin được nguồn xác nhận với giả định hoặc kết quả thử nghiệm nội bộ.
4. Không bịa nguồn, kết quả benchmark, công thức hoặc khả năng công nghệ.
5. Không tự tuyên bố một phương pháp là tốt nhất khi chưa so sánh bằng tiêu chí phù hợp.
6. Ghi nguồn ngắn gọn ở tài liệu kỹ thuật hoặc quyết định kiến trúc liên quan.
7. Với phương pháp được tự thiết kế để đáp ứng nghiệp vụ, phải ghi rõ đây là quyết định thiết kế nội bộ và kiểm thử bằng oracle độc lập.
8. Kiểm tra tính tương thích và phiên bản thực tế trước khi tích hợp SDK/API.

Không nhất thiết tìm paper cho từng dòng code thông thường. Chỉ yêu cầu nguồn cho các quyết định kỹ thuật quan trọng, thuật toán, phương pháp và công thức có ý nghĩa.

## RULE 04 — Thực hiện chính xác nhiệm vụ được giao

Codex phải:

- Đọc kỹ prompt trước khi thực hiện.
- Xác định phạm vi, đầu vào, đầu ra và điều kiện nghiệm thu.
- Chỉ sửa các thành phần liên quan trực tiếp.
- Không tự bổ sung tính năng.
- Không tự thay đổi kiến trúc đã phê duyệt.
- Không thực hiện tác vụ ngoài phạm vi.
- Không giả định một công việc đã PASS khi chưa chạy kiểm thử.
- Không tạo thêm nhiều prompt, scripts hoặc bản thử nghiệm ngoài kế hoạch.

Nếu phát hiện vấn đề ngoài phạm vi nhiệm vụ, phải báo cáo rõ. Chỉ tự xử lý khi đó là lỗi trực tiếp ngăn hoàn thành nhiệm vụ và phương án sửa không thay đổi kiến trúc hoặc quyền hạn đã giao.

Không được sửa một lỗi bằng cách tạo ra nhiều cơ chế fallback, validation hoặc adapter trùng nhau.

## RULE 05 — Kiểm soát overengineering toàn dự án

Đây là quy tắc ưu tiên cao.

ChatSAR là MVP demo, không phải nền tảng doanh nghiệp.

Bắt buộc:

- Chọn giải pháp đơn giản nhất đáp ứng đầy đủ yêu cầu.
- Không tự tạo microservices khi modular monolith đáp ứng được.
- Không tự bổ sung framework, agent, queue, cache hoặc database mới nếu chưa chứng minh nhu cầu.
- Không xây nhiều router, query engines hoặc verification engines cạnh tranh.
- Không thêm abstraction chỉ để chuẩn bị cho khả năng chưa được yêu cầu.
- Không tối ưu sớm khi chưa có số liệu về hiệu năng.
- Không tạo nhiều cấu trúc thư mục chỉ để trông chuyên nghiệp.
- Mọi dependency mới phải có lý do và lợi ích rõ ràng.

Trước khi bổ sung một thành phần lớn, tự đánh giá:

- Chức năng này có thực sự cần cho MVP không?
- Có thể dùng thành phần hiện có không?
- Có làm hệ thống khó bảo trì hơn không?
- Có tạo thêm chi phí hoặc điểm lỗi không?
- Có nằm trong kế hoạch đã phê duyệt không?

Nếu không có lý do đủ mạnh thì không bổ sung.

## RULE 06 — Tuân thủ tuyệt đối kế hoạch dự án

Đọc và sử dụng `docs/ChatSAR_MASTER_PLAN.md` (Master Plan), `docs/IMPLIMENT_PLAN.md` (Implementation Plan) làm cơ sở thực hiện.

Thứ tự ưu tiên:

1. Yêu cầu trực tiếp mới nhất của người dùng.
2. Rules.md và các giới hạn bảo mật, an toàn dữ liệu.
3. Implementation Plan đã được phê duyệt.
4. Master Plan.
5. Tài liệu kỹ thuật và quyết định kiến trúc bổ sung.

Nếu hai tài liệu có nội dung mâu thuẫn đáng kể, phải nêu rõ xung đột trước khi thay đổi chức năng.

Không tự ý:

- Mở rộng phạm vi MVP.
- Thay đổi mô hình dữ liệu hoặc API contracts đã khóa.
- Bỏ qua acceptance gates.
- Đổi nhà cung cấp AI.
- Gọi thêm cloud services.
- Thêm chức năng ngoài kế hoạch.

Khi phát hiện một thiết kế có vấn đề, phải giải thích nguyên nhân, đề xuất phương án và tác động trước khi thay đổi quyết định đã được phê duyệt.

## RULE 07 — Làm việc trên một source dự án chính

Thư mục nguồn chính thức:

`C:\Work\ChatSAR`

Bắt buộc:

- Làm việc trực tiếp trong repository chính.
- Không tạo thêm bản sao source code, repository phụ, thư mục backup hoặc các bản project song song.
- Không tạo môi trường staging riêng nếu không có yêu cầu.
- Không nhân bản hệ thống để thử nghiệm một chức năng nhỏ.
- Không tạo thêm cấu hình runtime cạnh tranh.
- Dùng Git để quản lý lịch sử thay đổi code.

Kiểm thử được thực hiện trên code của repository chính, với test fixtures và dữ liệu kiểm thử được cô lập ở mức cần thiết.

**Giới hạn an toàn:** Git chỉ khôi phục source đã commit, không tự động khôi phục database, Docker volumes, file upload hoặc trạng thái runtime.

Vì vậy, không được làm các thao tác có nguy cơ mất dữ liệu mà chỉ dựa vào khả năng rollback Git.

Các thao tác thay đổi dữ liệu phải an toàn, có migration/rollback hoặc backup phù hợp khi thực sự cần.

## RULE 08 — Quản lý Docker gọn gàng

- Chỉ dùng Docker Compose project chính thức của ChatSAR.
- Không tự tạo nhiều Compose projects hoặc Docker environments để test.
- Không sử dụng project name, volumes, ports gây xung đột ứng dụng khác.
- Chỉ tạo các containers thực sự cần thiết.
- Không build lại Docker image nếu không có thay đổi yêu cầu rebuild.
- Ưu tiên cache phù hợp để giảm thời gian build.
- Không tạo nhiều bản image không còn mục đích sử dụng.
- Không tự tải lại model weights đã có.
- Sau khi hoàn tất công việc, kiểm tra container và image dư thừa của ChatSAR.

Chỉ được dọn những tài nguyên đã xác định rõ thuộc ChatSAR, không còn sử dụng và không cần cho rollback.

**Nghiêm cấm tự động:**

- Xóa Docker volumes chứa dữ liệu.
- Dùng `docker system prune -a --volumes`.
- Dùng `docker volume prune` trên host dùng chung.
- Dọn images, networks hoặc containers của dự án khác.
- Xóa model cache, database hoặc dữ liệu người dùng.

Không được ảnh hưởng ShopQuery AI, Langfuse đang hoạt động hoặc những dịch vụ khác trên máy.

Nếu cần hành động phá hủy hoặc làm mất khả năng rollback, phải xin xác nhận.

## RULE 09 — Quản lý Git và GitHub

Codex chịu trách nhiệm quản lý Git/GitHub cho ChatSAR trong phạm vi quyền truy cập được cung cấp.

Quyền được giao cho các nhiệm vụ tiếp theo gồm kiểm tra trạng thái, tạo branch khi cần, commit/push phần thay đổi đã kiểm tra, tạo Pull Request (đề nghị hợp nhất mã), kiểm tra CI (kiểm tra tự động), phát hiện conflict (xung đột mã), đối chiếu local/remote và báo cáo repository. Chỉ dọn branch tạm sau khi xác minh đã hợp nhất, không còn cần thiết và không gây mất dữ liệu.

Người dùng giữ quyền phê duyệt merge thay đổi lớn, hành động phá hủy, thay đổi quyền repository và quyết định ngoài kế hoạch. Việc giao quản lý GitHub không cấp quyền tự mở rộng kiến trúc, triển khai tính năng hoặc bỏ qua nghiệm thu.

Repository:

`https://github.com/MinhHoang1403/ChatSAR`

Nhánh chính: `main`.

Quy tắc làm việc:

**Thay đổi nhỏ:**

- Có thể làm trực tiếp trên `main`.
- Kiểm tra diff, chạy các tests liên quan.
- Commit gọn, rõ chức năng.
- Push lên GitHub sau khi xác nhận hoàn tất.

**Thay đổi lớn hoặc có rủi ro:**

- Tạo feature branch ngắn hạn.
- Thực hiện công việc trên cùng repository.
- Không tạo bản sao project.
- Chạy kiểm thử và kiểm tra diff.
- Tạo Pull Request khi phù hợp.
- Chỉ merge khi đạt nghiệm thu và được người dùng phê duyệt.

**Nguyên tắc chung:**

- Không force push.
- Không rewrite lịch sử `main`.
- Không tự xóa repository.
- Không tự xóa branches/tags quan trọng.
- Không commit secrets hoặc dữ liệu nhạy cảm.
- Không tạo commit cho những thay đổi chưa được kiểm tra.
- Không ghi kết quả kiểm thử không có thật.
- Sau mỗi nhiệm vụ hoàn thành, commit/push phần thay đổi hợp lệ.
- Xác nhận local HEAD và remote commit SHA khi push.
- Báo cáo Git status, branch, commit SHA và kết quả push.

Trường hợp có lỗi, phải sửa và kiểm tra lại trước khi báo cáo hoàn thành.

## RULE 10 — Quản lý repository Public

GitHub ChatSAR là Public, do đó phải kiểm soát nội dung trước mỗi push.

Không đưa lên repository:

- API keys và credentials.
- `.env` chứa secrets.
- Google OAuth client secrets.
- Company tokens.
- Database passwords.
- Langfuse secret keys.
- Dữ liệu nội bộ chưa được phép công khai.
- Raw user documents chứa thông tin cá nhân.
- Model weights/cache.
- Database dumps.
- Log chứa thông tin nhạy cảm.

Dùng `.env.example` với placeholder, tuyệt đối không chứa giá trị thật.

Kiểm tra cả staged diff trước khi commit. Nếu phát hiện bí mật, dừng việc push và xử lý an toàn; không chỉ xóa secret khỏi commit mới nếu nó đã từng bị công khai.

## RULE 11 — Giải thích bằng tiếng Việt

Mọi báo cáo, giải thích, phân tích lỗi và đề xuất gửi người dùng phải bằng tiếng Việt.

Khi dùng thuật ngữ tiếng Anh, phải giải thích ngắn gọn bằng tiếng Việt, ví dụ:

- Regression test: kiểm thử để tránh lỗi cũ tái xuất hiện.
- Rollback: khôi phục về trạng thái trước.
- Grounding: đối chiếu thông tin với dữ liệu có căn cứ.
- Overengineering: thiết kế quá phức tạp so với nhu cầu.
- Oracle: kết quả chuẩn độc lập để đối chiếu.

Không trả lời bằng quá nhiều thuật ngữ chuyên ngành khi có thể giải thích đơn giản hơn.

## RULE 12 — Kiểm thử và sửa lỗi tận gốc

- Test phải đối chiếu đúng hành vi được yêu cầu.
- Không coi test PASS là bằng chứng toàn bộ sản phẩm đúng.
- Không sửa expected result chỉ để vượt test.
- Không hardcode theo tên dataset, ngành hoặc một câu hỏi cụ thể.
- Không sửa prompt liên tục khi chưa phân tích nguyên nhân.
- Khi có lỗi, xác định đúng tầng gây lỗi và đưa ra phương án giải quyết.
- Kiểm tra tác động đến các chức năng liên quan.
- Không tuyên bố model-live PASS nếu chỉ chạy mock.
- Không dùng một cách sửa tạm làm giải pháp chính thức mà không giải thích giới hạn.

Ưu tiên sửa đúng nguyên nhân, giữ kiến trúc nhất quán.

## RULE 13 — Quy tắc sử dụng AI providers và chi phí

ChatSAR sử dụng các công nghệ được mô tả trong kế hoạch.

Codex không được tự ý:

- Gửi dữ liệu thật lên cloud.
- Tiêu thụ Gemini/LlamaParse credits ngoài ngân sách.
- Đổi model hoặc endpoint mặc định.
- Tải model lớn mà không kiểm tra model hiện có.
- Bật tính năng fallback làm tăng chi phí không kiểm soát.
- Gửi secrets hoặc dữ liệu nhạy cảm vào Langfuse.

Cloud calls trả phí mặc định tắt cho đến khi người dùng phê duyệt hạn mức cụ thể.

## RULE 14 — Quản lý tài liệu và thư mục

- Chỉ giữ các tài liệu còn giá trị sử dụng.
- Không tạo nhiều báo cáo trùng lặp.
- Không tạo các file backup như `file_old`, `file_final`, `file_new`.
- Không nhân bản test fixtures.
- Không tạo script tạm thời rồi để tồn tại không có mục đích.
- Không xóa file chỉ vì chưa thấy được sử dụng; phải kiểm tra references trước.
- Nếu cần cập nhật kế hoạch, sửa tài liệu chính thức phù hợp thay vì tạo bản sao mới.

## RULE 15 — Cách thực hiện mọi prompt Codex

Trước khi bắt đầu:

1. Đọc yêu cầu.
2. Đọc Rules.md và phần Implementation Plan liên quan.
3. Kiểm tra trạng thái repository.
4. Xác định phạm vi thay đổi.
5. Xác định các điều kiện nghiệm thu.
6. Thực hiện đúng nhiệm vụ.
7. Chạy kiểm thử cần thiết.
8. Kiểm tra diff và file không mong muốn.
9. Commit/push nếu công việc hoàn thành hợp lệ.
10. Báo cáo kết quả chính xác.

Với nhiệm vụ lớn, chia thành các bước nhỏ có dependency rõ ràng, không tự mở rộng phạm vi.

Không giả định rằng một prompt dài cho phép tùy ý thực hiện tất cả công việc liên quan.

---
