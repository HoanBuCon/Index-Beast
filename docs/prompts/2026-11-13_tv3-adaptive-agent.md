# Meta-prompt · Agent thích ứng của IndexBeast

## Vai trò

Bạn là Backend/AI Engineer hỗ trợ TV3 MinhMuc của nhóm 4 Hollows. Triển khai trực tiếp trong pipeline LangGraph và LangChain hiện có của IndexBeast.

## Ngữ cảnh

IndexBeast đã nhận diện ý định, chọn công cụ từng bước và hỏi bổ sung qua hội thoại. Ca `IB-GS-086` cho thấy truy vấn viết lại mất dấu phẩy có thể bị chặn. Người dùng muốn Agent tự hiểu lỗi gõ, kiểm tra tên với kho, chọn khi nào tìm thêm hoặc hỏi lại, và giữ tiến độ khi xử lý nhiều mục tiêu.

## Ràng buộc

- Cho mô hình chọn ý định, hành động, câu hỏi bổ sung, truy vấn, công cụ và mục tiêu. Backend kiểm schema, nguồn gốc thực thể, quyền, spoiler, ngân sách, citation và phép tính.
- Chấp nhận khác biệt dấu phẩy/khoảng trắng khi đối chiếu tên. Với lỗi gõ, chỉ tự sửa khi tên được bằng chứng trong kho xác nhận rõ. Hỏi lại nếu các ứng viên hợp lý dẫn tới câu trả lời khác nhau. Bảo toàn số, patch, phủ định và điều kiện người chơi.
- Chỉ dùng kế hoạch tường minh cho câu nhiều mục tiêu. Cho Agent cập nhật kế hoạch từ kết quả công cụ. Giữ mục đã có bằng chứng qua lượt hỏi bổ sung của cùng yêu cầu và kiểm lại chính sách trước khi tái sử dụng.
- Dùng luồng JSON/SSE, `turn_id`, giới hạn cuộc hội thoại và chính sách Tavily hiện có. Giới hạn thử thật tối đa 5 lượt DeepSeek với Tavily Auto sau khi kiểm offline.

## Đầu ra

Triển khai code và test hồi quy, báo kết quả offline và thử thật theo từng ca, ghi rõ collection và phạm vi thử, lưu handover và lệnh chạy lại.
