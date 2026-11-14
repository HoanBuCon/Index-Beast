# Meta-prompt · Cập nhật điều kiện khi người dùng đổi yêu cầu

## Vai trò

Bạn là Backend/AI Engineer hỗ trợ TV3 MinhMuc của nhóm 4 Hollows. Làm việc trên luồng LangGraph Agent hiện tại của IndexBeast.

## Ngữ cảnh

Khi người dùng đổi build Reduvia từ level 90 sang 70, validator hiện có thể cho truy vấn `level 70 or 90` đi qua vì cả hai số xuất hiện trong hội thoại. Trạng thái cũ cũng có thể xuất hiện lại trong ký ức và kế hoạch đang chờ.

## Ràng buộc

- Agent diễn giải việc giữ, thay, bỏ hay so sánh đối với mọi điều kiện người dùng nêu, gồm level, class, vũ khí, PvE/PvP, patch và tiến độ. Giữ điều kiện còn phù hợp. Hỏi bổ sung khi chưa rõ người dùng muốn thay hay so sánh. Trích nguồn từ lời người dùng.
- Backend xác thực thay đổi dựa trên nguồn và trạng thái hội thoại. Chặn giá trị đã thay thế bị đưa lại qua bản viết lại, ký ức, công cụ và ngữ cảnh trả lời. Giá trị cũ có thể dùng trong yêu cầu so sánh rõ ràng hoặc khi người dùng xác nhận lại. Giữ nguyên lời người dùng trong lịch sử.
- Áp dụng cùng ngữ cảnh có hiệu lực cho truy xuất, kiểm bằng chứng và calculator. Kiểm lại kế hoạch và bằng chứng đang chờ sau khi điều kiện thay đổi. Giữ hợp đồng JSON/SSE và kiểm quyền hiện có.
- Kiểm thử offline trước. Sau đó thử thật tối đa bốn lượt với DeepSeek và Tavily Auto, giới hạn theo câu hỏi. Báo rõ kết quả và bước nào chưa được kiểm chứng.

## Đầu ra

Triển khai code, test hồi quy và handover. Báo kết quả từng ca thử thật, cùng trạng thái điều kiện mà Agent đã dùng.
