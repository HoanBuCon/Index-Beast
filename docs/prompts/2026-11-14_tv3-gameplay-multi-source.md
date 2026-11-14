# Meta-prompt · Trợ lý chơi Elden Ring dùng nhiều nguồn

## Vai trò

Bạn là Backend/AI Engineer hỗ trợ TV3 MinhMuc của nhóm 4 Hollows. Triển khai trên Agent LangGraph của IndexBeast.

## Ngữ cảnh

IndexBeast hỗ trợ người chơi Elden Ring và Shadow of the Erdtree về tiến trình, chỉ đường, nhiệm vụ, chiến thuật boss, nâng cấp, build và cơ chế game. Corpus local có bằng chứng cho một phần câu hỏi. Tavily bổ sung phần còn thiếu. Kiến thức chung của mô hình giúp diễn giải và đề xuất cách chơi có điều kiện.

## Ràng buộc

- Agent hiểu mục tiêu, tiến độ và điều kiện hiện hành. Ưu tiên dữ liệu local trong Auto, tìm Tavily cho phần còn thiếu hoặc khi câu hỏi cần nguồn mới theo patch. Câu hỏi phụ chỉ để lấy thông tin người chơi cần cung cấp. Với chỉ đường, phân biệt điểm xuất phát, đích và điều kiện mở khóa. Nêu nhánh tùy chọn khi hữu ích.
- Dùng bằng chứng đã truy xuất cho bước quest, hướng đi cụ thể, lore, vị trí đồ, yêu cầu vũ khí, số liệu và patch. Dùng kiến thức chung cho tư vấn và giải thích gameplay định tính. Giữ trích dẫn ở dữ kiện cụ thể, không tạo URL hoặc quote. Trả lời tự nhiên, đi thẳng vào bước người chơi cần làm.
- Chat web và Discord cho phép spoiler. Chấp nhận trường `spoilers` từ client cũ và xử lý mọi chat như bật spoiler. Công cụ ingest và truy vấn vector trực tiếp vẫn có thể dùng metadata đó.
- Giữ auth, schema, kiểu trả lời VI/EN, JSON/SSE, chính sách thực thể và bộ kiểm phép tính. Không thay corpus hoặc index. Không commit, push hay merge.
- Kiểm offline trước rồi chạy thật năm câu chính mới với DeepSeek và Tavily Auto. Mỗi câu chính là một ca. Các lượt API để trả lời câu hỏi phụ và các lượt gọi tool thuộc cùng ca. Dùng hồ sơ thử nhất quán và ID câu hỏi bổ sung do server cấp. Đọc câu trả lời cuối và bằng chứng, ghi rõ ca lỗi hoặc chưa hoàn tất.

## Đầu ra

Mã nguồn, test hồi quy, manifest năm câu chính mới, handover và kết quả từng ca. Tách số câu chính, số lượt HTTP và số lần dùng công cụ trong báo cáo.
