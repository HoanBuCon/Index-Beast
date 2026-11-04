# TV4 · Bỏ đánh giá dưới câu trả lời

Ngày: 05/11/2026 (Asia/Saigon). Nhánh thực hiện: `docs/s2-tv4-nap-du-lieu-local`. Chưa commit/push.

## Yêu cầu và phạm vi

Người dùng yêu cầu bỏ dòng “Câu trả lời có hữu ích?” và hai nút đánh giá ở dưới câu trả lời. Chỉ sửa phần hiển thị frontend TV4 cùng tài liệu bàn giao, không sửa backend, bot, planning hoặc hợp đồng API của thành viên khác.

## Thay đổi

- `web/src/components/chat/MessageList.tsx`: gỡ import và chỗ render `FeedbackButtons`. Giữ các ghi chú và các phần hiển thị câu trả lời, citation/popover, Markdown an toàn, ảnh và trạng thái đang chờ/chưa hoàn tất.
- `web/tests/answerMedia.test.ts`: kiểm tra SSR không còn câu hỏi đánh giá hoặc nút đánh giá trong câu trả lời.
- Không xóa component `FeedbackButtons`, hàm API feedback hoặc dữ liệu đánh giá đã lưu. Tác vụ này chỉ bỏ khối thao tác khỏi giao diện chat theo yêu cầu.

## Kiểm tra và cách dùng

- `npm.cmd test`: 34/34 test đạt, có kiểm tra SSR không còn khối đánh giá.
- `npm.cmd run build`: TypeScript và Vite production đạt.
- `npm.cmd run format:check`: đạt.
- Kiểm tra diff, mã hóa UTF-8 và liên kết handover mới đạt. Chưa kiểm tra trực quan trong trình duyệt; không gọi API thật hoặc LLM.

Tải lại web đang chạy, mở câu trả lời: dòng hỏi đánh giá và hai nút không còn xuất hiện. Không cần nạp lại dữ liệu hoặc tạo lại index.
