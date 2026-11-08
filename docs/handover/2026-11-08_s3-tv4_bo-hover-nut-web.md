# TV4 · Bỏ nền hover nút Web

Ngày: 08/11/2026 (Asia/Saigon).

Theo yêu cầu người dùng, nút Web trong ô nhập không hiện nền sáng khi rê chuột.
Sửa riêng `web/src/styles/refinement.css`, override hover button chung bằng nền trong suốt, không border/shadow.
Giữ màu theo chế độ, thao tác đổi chế độ và focus bàn phím; không sửa khung chat hoặc nút gửi/dừng.

Kiểm tra định dạng CSS và `git diff --check` đạt. Đây là thay đổi CSS nhỏ, không thêm test mô phỏng lại CSS.
Tải lại web rồi rê chuột vào Web: ON/ALWAYS để xem; bấm vẫn đổi chế độ như trước.
Không gọi LLM, không thay cấu hình/API/bot, không commit/push.
