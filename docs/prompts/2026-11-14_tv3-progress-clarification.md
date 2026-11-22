# Meta-prompt · Nối lượt hỏi đường sau khi người chơi trả lời bổ sung

## Vai trò

Bạn là Backend/AI Engineer hỗ trợ TV3 MinhMuc của nhóm 4 Hollows. Triển khai trong luồng Agent LangGraph hiện tại của IndexBeast.

## Ngữ cảnh

Người dùng hỏi “giờ đi đâu tiếp”, nhận câu hỏi trong khung phụ rồi trả lời “vừa xong tutorial”. Lượt `/api/v1/chat/stream` dừng ở `agent_decision` với HTTP 502. Stack trace xác định bước lỗi. Quy tắc yêu cầu tên thực thể ở mọi lượt tìm kiếm nối tiếp có thể chặn trường hợp người chơi chỉ biết mốc tiến độ.

## Ràng buộc

- Đưa yêu cầu gốc và câu hỏi đang chờ cho LLM để diễn giải câu trả lời tự do. Dùng thông tin do người dùng xác nhận và giữ nguyên văn trong hội thoại.
- Cho phép tìm đường hoặc quest với `entities=[]` khi mốc tiến độ có căn cứ trong lượt người dùng và yêu cầu gốc đã được giữ. Đại từ chưa rõ chủ thể vẫn cần hỏi lại. Giữ nguyên kiểm tra quyền hội thoại, nguồn gốc dữ kiện, số liệu và trích dẫn.
- Cho Agent dùng tên địa điểm suy đoán trong truy vấn tìm kiếm. Câu hỏi đã giải nghĩa giữ trạng thái người chơi chưa xác định. Hướng dẫn đường đi theo điều kiện dựa trên bằng chứng tìm được.
- Ghi mã lý do validator từ chối để đối chiếu request ID. Tránh ghi nguyên văn câu hỏi, output mô hình hoặc thông tin riêng vào log lỗi. Kiểm bằng model và nguồn giả lập qua luồng JSON/SSE.

## Đầu ra

Cập nhật validator, prompt và kiểm thử hồi quy. Bao gồm đúng hai lượt đã báo, ca đại từ mơ hồ, dữ kiện tiến độ bịa, địa danh suy đoán và lỗi schema/JSON. Ghi cách kiểm, kết quả thực tế và giới hạn của bằng chứng trong handover.
