# Chỉ dẫn Codex cho ChatSAR

- Mỗi phiên làm việc mới, trước khi thực hiện thay đổi và đặc biệt trước khi sửa code, bắt buộc đọc toàn bộ [Skills/Rules.md](Skills/Rules.md). Không bỏ qua hoặc dựa vào trí nhớ của phiên trước.
- Đọc phần kế hoạch tương ứng trong [docs/IMPLIMENT_PLAN.md](docs/IMPLIMENT_PLAN.md) và [docs/ChatSAR_MASTER_PLAN.md](docs/ChatSAR_MASTER_PLAN.md). Trước lần sửa mã nguồn đầu tiên, đọc toàn bộ Implementation Plan theo mục 0.1. Dùng đúng tên file hiện có, không tạo bản sao theo tên cũ trong tài liệu.
- Tuân thủ Rules.md về chất lượng code, tránh thiết kế quá phức tạp, một source chính, Docker, an toàn dữ liệu, Git/GitHub Public và chính sách cloud/chi phí. Báo cáo bằng tiếng Việt.
- Kiểm tra trạng thái Git trước khi làm; xác định phạm vi/nghiệm thu, kiểm tra diff và secrets, chạy kiểm tra liên quan rồi commit/push phần thay đổi hợp lệ theo RULE 09–10. Báo branch, SHA local/remote và trạng thái đồng bộ.
- Nếu yêu cầu mới mâu thuẫn đáng kể với quy tắc hoặc kế hoạch, báo cáo rõ trước khi thay đổi kế hoạch đã phê duyệt; không tự mở rộng phạm vi hay bỏ qua điều kiện nghiệm thu.
- Hiện chỉ được thiết lập Rules/tài liệu/GitHub. Chưa được lập trình ChatSAR, tạo container, triển khai hoặc gọi API trả phí. Chỉ bắt đầu milestone khi có yêu cầu mới rõ ràng và đủ phê duyệt. Không tác động ShopQuery AI hoặc dịch vụ khác trên máy.
