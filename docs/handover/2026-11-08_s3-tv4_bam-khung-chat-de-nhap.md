# TV4 · Bấm khung chat để nhập

- Nhánh: `feature/s3-tv4-web-streaming-sse`. Phạm vi frontend TV4, chỉ `web/src/components/chat/MessageInput.tsx` và bàn giao.
- Nguyên nhân: chỉ textarea nhận focus; vùng padding/nền khung không chuyển focus vào ô nhập.
- Thêm xử lý click ở composer để focus textarea khi bấm vùng trống hoặc viền. Bỏ qua textarea (giữ vị trí con trỏ), button/link/input/select/label (giữ thao tác riêng) và khi đang chọn chữ. Không đổi giao diện, logic gửi, Enter/Shift+Enter, Web hoặc dừng.
- Kiểm tra Chrome/CDP với component thật trong fixture cục bộ ở viewport 1440 và 360: bấm nền gần góc khung rồi gõ được ngay; bấm textarea giữ caret; nút Web giữ focus riêng; nút dừng vẫn gọi callback. Kiểm tra Esc và ảnh dừng vẫn đạt. Script nằm ở `web/.taste-skill/check-composer-focus.mjs` (Git bỏ qua). Không gọi API thật.
- Build, format:check và 2/2 test composer/searchToggle đều đạt. Diff/UTF-8/link bàn giao đạt. Chưa kiểm tra trên thiết bị cảm ứng thật.
- Cách dùng: tải lại web, bấm vùng trống trong khung “Hỏi INDEX BEAST” rồi gõ. Không cần bấm trúng dòng placeholder.
- Giữ chú thích hiện có; không sửa backend/bot/planning hoặc phần TV1–TV3, không commit/push hay sửa develop.
