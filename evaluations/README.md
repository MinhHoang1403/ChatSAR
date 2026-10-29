# Benchmark và oracle độc lập

Fixtures là dữ liệu tổng hợp thuộc năm domain logistics, khách sạn, năng lượng, nông nghiệp và thư viện. Không chứa dữ liệu thật của người dùng/công ty. `manifest.json` lưu câu hỏi, kiểu, quyền, revision, expected và SQL oracle viết tay trước khi có compiler ứng dụng. SQL này chỉ được evaluation harness đọc, không phải đường nhận SQL trong runtime.

`development` dùng phát triển; `regression` kiểm tra lỗi/biến thể; `held-out` là domain thư viện được khóa trước implementation và không dùng để tuning. Người tạo fixtures biết labels, nên không tuyên bố đây là blind benchmark do người thứ ba đánh giá. Nếu xem case held-out để sửa compiler/prompt, chuyển case sang regression và cần bộ mới trước công bố kết quả held-out.

`checksums.json` khóa byte của fixtures và manifest. Thay checksum phải có lý do review; không tự làm mới checksum trong test để hợp thức hóa thay đổi. Oracle không import `app`, không gọi compiler hoặc model. Expected Decimal được đối chiếu thêm bằng phép cộng/chia Decimal độc lập, không suy gold từ output thực tế.

Harness chạy PostgreSQL thật trong đúng service `db` của Compose `chatsar`, nạp fixtures trong một transaction rồi rollback. Không tạo DB/container/Compose project thứ hai và không động vào dữ liệu dự án khác. Negative semantic cases là acceptance đầu vào cho các mốc sau; chưa có app thì ghi NOT_RUN, không tính oracle PASS thành semantic PASS.

Các cases ở đây là baseline khởi đầu cho Phase 1, không thay thế bộ 170 cases đề xuất hoặc acceptance model-live/browser. Chạy `py -3.11 -m unittest discover -s evaluations/tests -v` để kiểm manifest/checksums/Decimal; `py -3.11 -m evaluations.oracle` để kiểm oracle PostgreSQL.
