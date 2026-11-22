# Sửa review bot (S5 · TV1) · 2026-11-22

Nguồn: `2026-11-17_s5-tv2_ra-soat-ma-toan-he-thong.md`, mục 7, 8, 15. Nhánh `fix/s5-tv1-review-bot`.

## Đã sửa

- **#7** `/ask` gửi text thô. Chuyển `sanitizeMentions` sang `bot/src/utils/redact.ts`, dùng ở `/ask` và handler tin nhắn. Hỏi tiếp trong thread (`followup.ts`) chỉ nhận chuỗi đã qua hai đường này (câu hỏi gốc, câu hỏi thread), nên không cần redact thêm.
- **#8** `guildChannelCache`: mỗi guild có bộ đếm phiên bản. `invalidate` tăng phiên bản, xóa entry và promise đang chạy. Lần tải cũ không ghi cache nếu phiên bản đã đổi, và `has()` đọc lại khi phiên bản đổi trong lúc chờ.
- **#15** Link chia sẻ: nhãn nút và footer lấy thời hạn từ `expires_at` (`shareTtlLabel` trong `utils/format.ts`: phút/giờ/ngày). Không đọc được thì dùng chữ trung tính ("trong thời gian giới hạn").

## Quyết định

- Thời hạn là thời gian còn lại tính từ lúc nhận phản hồi (làm tròn), không phải giờ tuyệt đối, để khỏi lệ thuộc múi giờ.
- Các chuỗi "24 giờ" trong `followup.ts` là TTL riêng của nút/thread Hỏi tiếp do bot tự quản, giữ nguyên.

## Kiểm tra

- `npm run typecheck`: sạch. `npm test`: 78 pass, 0 fail (3 test mới, đã thấy đỏ trước khi sửa). `prettier --check .`: sạch.

## Chưa kiểm

- Chưa chạy bot thật với Discord/API thật.
