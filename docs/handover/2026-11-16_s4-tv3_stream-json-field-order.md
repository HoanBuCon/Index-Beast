# TV3 · Chấp nhận thứ tự trường JSON hợp lệ trong SSE

Ngày 16/11/2026 · Nhánh `feature/s4-tv3-api-reranker`.

## Phạm vi và kết quả

Khắc phục parser SSE từ chối một JSON RAG hợp lệ khi trường `answer` không đứng đầu. Decoder trả lời không stream chấp nhận thứ tự trường tùy ý, nhưng parser stream tìm riêng mẫu mở đầu `{"answer":...}` và báo lỗi sau 64 ký tự nếu chưa thấy mẫu (`backend/app/rag/generator.py`, hàm `answer_prefix`). Đây là lỗi hợp đồng parser đã xác nhận qua mã và kiểm thử; chưa có bằng chứng cho thấy nó là nguyên nhân của hội thoại người dùng hỏi “cách nhanh nhất để endgame”, nhận câu hỏi bổ sung rồi trả lời “phá đảo nhanh nhất”. Chưa có trace gần thời điểm đó hoặc kết quả chạy trực tiếp để kết luận sự cố cụ thể đã được giải quyết.

## Thay đổi

- SSE chỉ chuyển sang giữ buffer khi chưa phát token đáp án và parser tiền tố không nhận ra trường `answer` ở vị trí đầu. Tại EOF, toàn bộ JSON vẫn đi qua decoder giới hạn kích thước, schema nghiêm ngặt và kiểm tra citation/evidence hiện có. Không phát metadata JSON ra giao diện.
- Nếu đã phát nội dung đáp án, lỗi tiền tố vẫn kết thúc stream theo cơ chế hiện có; không thể rút lại token đã gửi.
- Thêm kiểm thử cho JSON hợp lệ có `answer` sau `evidence`, và các trường hợp JSON cắt cụt, khóa trùng, citation sai để xác nhận buffer không bỏ qua validation.

## Kiểm tra

- Bộ backend unit: **1.186 passed, 20 skipped, 2 warnings**.
- Nhóm test tập trung cho output, chat và recovery schema: **159 passed**.
- Ruff cho `backend/app/rag/generator.py` và `backend/tests/unit/test_live_chat.py`: đạt.
- `git diff --check` cho thay đổi handover/index: đạt; liên kết index và mã hóa UTF-8 đã kiểm tra.
- Đã chạy đúng một ca live được cho phép: SSE trả HTTP 200 và sự kiện `done`, không có lỗi định dạng hoặc retry. Agent trả lời thẳng câu hỏi “cách nhanh nhất để endgame”, nên ca này không phát sinh làm rõ và không gửi lượt nối tiếp “phá đảo nhanh nhất”. Vì vậy, nhánh hội thoại hai lượt ban đầu chưa được tái hiện.
- Ca live dùng DeepSeek với 10 lượt gọi logic, Jina thành công với 30/30 ứng viên, Tavily search và extract đều thành công; corpus giữ nguyên 34.070 điểm. Runner cô lập đặt giới hạn gọi Agent/công cụ thành không giới hạn; snapshot cấu hình dùng 4.096 token và thinking bật. Các khác biệt so với cấu hình Production vẫn chờ đối chiếu, nên kết quả không chứng minh cấu hình hoặc hội thoại Production tương đương.
- Câu trả lời có nội dung chưa hỗ trợ được khẳng định “nhanh nhất”. Đây là vấn đề chất lượng riêng, không phải lỗi định dạng JSON; lần chạy này không kết luận chất lượng câu trả lời.

## Tệp trong phạm vi

- `backend/app/rag/generator.py`
- `backend/tests/unit/test_live_chat.py`
- `docs/handover/README.md`
- Handover này.

## Còn lại

- Ca live được phép không tái hiện hội thoại làm rõ rồi nối tiếp ban đầu. Không kết luận đã xử lý xong sự cố đó; nếu cần chẩn đoán tiếp, phải có trace tương ứng hoặc một lần tái hiện được cho phép.
- Cấu hình runner cô lập chưa được chứng minh trùng với Production. Không dùng kết quả này để khẳng định chất lượng hoặc tính đúng của phát biểu “nhanh nhất”.
