# Phạm vi năng lực và nghiệm thu

Đây là hợp đồng phạm vi trước triển khai, không phải danh sách chức năng đã chạy. Kết quả thực tế nằm tại `PREFLIGHT.md`.

| Mốc | Phạm vi | Điều kiện để nghiệm thu |
|---|---|---|
| F1 | Health API, React shell, PostgreSQL/pgvector, migrations, oracle độc lập, CI | web/api/db healthy; restart; quyền reader; oracle; CI đúng SHA |
| F2 | Google login/logout, DB sessions, owner workspaces | Login Google thật + invalid tokens/CSRF + A/B isolation + restart |
| F3 | CSV/XLSX, review schema, immutable revision, catalog | Decimal/NULL/TEXT ID giữ nguyên; lỗi không bỏ dòng; atomic publish và restart |
| F4 | SQL một bảng, typed plan/binding/compiler/read-only, chat/history/provenance | Hai schema, oracle/negative tests, browser thật; model-live báo riêng |

Phase 1 hỗ trợ SELECT columns, COUNT_ROWS/COUNT_NON_NULL/COUNT_DISTINCT, SUM/AVG/MIN/MAX, AND/OR, EQ/NE/GT/GTE/LT/LTE/IN/IS_NULL/IS_NOT_NULL, GROUP BY, ORDER BY, LIMIT và thời gian có mốc xác định. JOIN chưa được triển khai trong Phase 1 dù grammar tổng thể có JOIN.

Không triển khai RAG, document ingestion, embedding/reranking, Hybrid/policy evaluator hoặc agents trong nhiệm vụ này. Không thực thi SQL tự do, DDL/DML, expressions/functions do model gửi, JOIN suy đoán, tự chuyển model hay cloud fallback.

Giới hạn ứng viên để kiểm thử: 20 MiB/file, 50.000 rows/sheet, 100 rows mặc định/500 rows tối đa, statement timeout 5 giây, IN tối đa 100 giá trị, cây filter sâu tối đa 8/nhiều nhất 100 nodes. Đây là giới hạn kỹ thuật đề xuất; latency/accuracy thực phải đo và được chốt trước nghiệm thu chất lượng cuối.

Ingestion hiện giới hạn thêm 100 cột, 250.000 ô, 20 sheets và 100 MiB nội dung ZIP giải nén. CSV hỗ trợ UTF-8/BOM và UTF-16 có BOM, các delimiter comma/semicolon/tab/pipe; encoding khác báo không hỗ trợ. XLSX không thực thi công thức: phải chuyển thành giá trị; số được đọc từ XML gốc bằng Decimal, không đi qua float. Ngày mơ hồ cần người dùng chọn format; numeric có giới hạn 38 chữ số/exponent để kiểm soát tài nguyên. NULL sentinel được xác nhận ở review; ô trống TEXT không tự biến thành NULL. Không có tự động suy/approve quan hệ.

Không coi health HTTP 200, tests mock hoặc oracle trên typed plans là bằng chứng hiểu câu hỏi tự nhiên đúng. SQL correctness và false refusal chấm trên câu hỏi in-scope, với denominator theo §19; không loại câu khó khỏi denominator để tăng tỷ lệ.

Phần F1–F4 hiện đã có code và kiểm thử độc lập, xem PREFLIGHT để biết chính xác mốc PASS/BLOCKED. Natural-language SQL mới có bằng chứng đúng trên 2 ca Gemini/2 schema; Knowledge chưa trả answer được nghiệm thu và gặp 403. Ngày/thời gian phải có giá trị exact ISO hoặc format review; chưa tự suy khoảng tháng từ câu tự nhiên. Runtime coverage guard là kiểm tra nhất quán proposal, không phải chứng minh hiểu câu hỏi đầy đủ. Google login/workspace live đã xác minh; chat/result browser E2E và benchmark rộng chưa đủ để nghiệm thu toàn bộ.
