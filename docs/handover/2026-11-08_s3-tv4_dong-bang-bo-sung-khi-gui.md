# TV4 · Đóng bảng trả lời bổ sung khi gửi

- Nhánh: `feature/s3-tv4-web-streaming-sse`. Phạm vi frontend TV4; không sửa API/backend/bot hoặc logic thành viên khác.
- `web/src/components/chat/ClarificationForm.tsx`: ẩn toàn bộ bảng và hướng dẫn ngay khi gửi bằng OK/Enter/Hủy, kể cả lúc request đang chờ. Giữ textarea mounted và draft trong state. Callback thành công giữ bảng đóng; callback false/lỗi mở lại, không xóa nội dung. Trạng thái disabled từ cha cũng ẩn bảng trong lúc retry qua nút thử lại của chat chính. Giữ chặn double-submit và hạn sử dụng câu hỏi.
- Auto-resize bỏ qua phần tử đang ẩn/chiều ngang 0 và đo lại khi bảng hiện, tránh ô nhập co sai khi thử lại. Không đổi màu, nền, kích thước hoặc nội dung câu trả lời.
- `web/tests/clarification.test.ts`: xác nhận bảng có hidden khi disabled; bộ test 4/4 đạt. Build TypeScript/Vite và Prettier đạt.
- Chrome/CDP với fixture component thật tại 1440/360: OK/Enter/Hủy đóng ngay, không gửi lặp, false trả lại draft nguyên văn và kích thước hợp lệ, success giữ đóng. Đã lưu screenshot lúc đang gửi tại `web/.taste-skill/clarification-closed-*.jpg`; script `check-clarification-close.mjs` nằm trong thư mục Git bỏ qua. Không gọi API thật/LLM; hủy request do hook trả false được xử lý như thất bại, chưa thử mạng thật.
- Cách kiểm tra: gửi câu trả lời bổ sung, bảng biến mất trong khi chat chính hiển thị chờ; nếu dừng/lỗi, bảng mở lại để sửa hoặc gửi lại. Callback trả false/throw không tiêu thụ draft.
- Giữ ghi chú cũ, không commit/push, không thay develop. Đã kiểm tra diff, UTF-8 và liên kết bàn giao.
