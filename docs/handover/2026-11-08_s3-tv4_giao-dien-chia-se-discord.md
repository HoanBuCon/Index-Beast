# TV4 · Đồng bộ giao diện trang chia sẻ Discord

Ngày: 08/11/2026 (Asia/Saigon). Nhánh: `fix/s3-tv4-giao-dien-chia-se-discord`.

## Yêu cầu và nguyên nhân

Trang mở từ link Discord thiếu nền và chữ nhỏ hơn trang chat chính. `SharedAnswerPage` dùng class `.document`,
chịu quy tắc paragraph 14 px và bố cục tài liệu; chưa dùng background của `.chat-panel`.
Chỉ sửa frontend TV4; giữ nguyên API chia sẻ, token, thời hạn, bot và nội dung trả lời.

## Thay đổi

- `web/src/pages/ChatPage.tsx`: riêng route `/answer` dùng thêm `chat-panel shared-answer-panel`,
  tái sử dụng nền chat và giữ sidebar/mobile inert hiện có. Các route About/admin không đổi class.
- `web/src/pages/SharedAnswerPage.tsx`: bỏ layout `.document`, dùng vùng cuộn `.chat-content` và `MessageList` sẵn có.
  Thu gọn tiêu đề; vẫn có thông báo chỉ đọc, hạn dùng, lỗi/thử lại, nguồn và link trở về trò chuyện.
- `web/src/styles/refinement.css`: metadata/footer cùng cột chat 760 px, chữ trả lời dùng quy tắc 18 px hiện có.
  Giữ nền/sidebar/composer của chat chính; trang chia sẻ không có ô nhập hoặc quyền gửi bằng token chia sẻ.

Không thêm dependency, không sửa backend/bot/planning/README gốc; không commit/push hoặc đổi develop.

## Kiểm tra

- Build TypeScript/Vite và Prettier check đạt.
- 7 test liên quan answer shares và clarification đạt.
- Trình duyệt thật ở 1440, 768, 360 px bằng fixture chặn riêng endpoint chia sẻ trong server kiểm tra:
  chữ paragraph 18 px, cùng ảnh nền patches, không tràn ngang, đúng nguồn, không có composer và bắt đầu đọc ở đầu trang.
  Kiểm tra thao tác mở nguồn bằng bàn phím. Đã xem ảnh desktop và 360 px.
- Script kiểm tra đầu bị socket ECONNRESET sau lượt 768 px; bổ sung xử lý socket trong script tạm rồi chạy riêng 360 px.
  Đây là lỗi harness kiểm tra, không thêm xử lý vào sản phẩm. Script và ảnh kiểm tra nằm trong thư mục Git ignore.
- Không gọi LLM/API thật hoặc tạo bản chia sẻ mới trong kiểm tra giao diện này.

## Cách xem và giới hạn

Giữ Vite/backend đang chạy, mở lại link Discord còn hạn rồi nhấn `Ctrl+F5` để xem giao diện mới.
Không cần đăng ký lại lệnh hoặc khởi động lại bot chỉ vì thay đổi frontend này.
Trang chia sẻ vẫn là bản chụp một câu trả lời từ Discord; nội dung có thể khác câu trả lời khi hỏi độc lập trên web.
Không tự chuyển link này thành hội thoại có quyền gửi hoặc mở toàn bộ lịch sử.
