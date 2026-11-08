# TV4 · Bỏ link mở nguồn trùng bên ngoài danh sách

Ngày: 08/11/2026 (Asia/Saigon).

## Phạm vi

Theo yêu cầu người dùng, bỏ các link “Mở nguồn ↗” đứng riêng bên phải từng nguồn.
Giữ số `[n]`, tiêu đề, nút xem trích đoạn và link “Mở trang nguồn ↗” bên trong popover.
Áp dụng chung cho chat chính và trang chia sẻ Discord, chỉ sửa frontend TV4.

## File thay đổi

- `web/src/components/chat/SourceList.tsx`: bỏ anchor trùng và import không dùng; cập nhật ghi chú đúng hành vi.
- `web/src/styles/refinement.css`: danh sách nguồn dùng một cột toàn chiều rộng; bỏ CSS riêng của anchor đã xóa.
- `web/tests/answerShares.test.ts`: kiểm tra danh sách không còn anchor; popover vẫn có link HTTP(S) hợp lệ,
  không có link javascript hoặc URL chứa credentials.

## Kiểm tra và sử dụng

Build TypeScript/Vite, Prettier check và 3 test answerShares đạt. `git diff --check` đạt.
Mở lại trang chat hoặc link chia sẻ còn hạn, tải lại trang; bấm tiêu đề nguồn để mở trích đoạn rồi mở trang gốc.
Không cần thay cấu hình, khởi động lại bot hoặc đăng ký lệnh. Không gọi LLM, không sửa backend/bot,
không commit/push. Thay đổi chỉ loại link lặp, không bỏ nguồn trích dẫn.
