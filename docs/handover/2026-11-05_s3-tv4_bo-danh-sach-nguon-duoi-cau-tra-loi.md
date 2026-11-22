# TV4 · Bỏ danh sách nguồn dưới câu trả lời

Ngày: 05/11/2026 (Asia/Saigon). Người dùng yêu cầu bỏ khối “Dấu vết trong kho lưu trữ” được đánh dấu trong ảnh.

## Phạm vi

- Chỉ thay đổi frontend TV4 và tài liệu bàn giao; không sửa backend, bot, hợp đồng API, dữ liệu hoặc pipeline của thành viên khác.
- `web/src/components/chat/MessageList.tsx`: bỏ import và chỗ render `SourceList` dưới câu trả lời. Giữ nguyên ghi chú, Markdown an toàn, citation trong nội dung và popover, ảnh minh họa, trạng thái chờ và nút feedback.
- Không xóa dữ liệu `sources`: trích dẫn `[n]` và việc kiểm tra nguồn ảnh vẫn dùng dữ liệu này.
- `web/tests/answerMedia.test.ts`: cập nhật kiểm tra SSR để khối danh sách nguồn không còn xuất hiện, tiếp tục kiểm tra citation và feedback hiện diện.
- Giữ component `SourceList.tsx` cùng CSS hiện có, không dọn các phần ngoài yêu cầu.
- Nhánh lúc thực hiện: `docs/s2-tv4-nap-du-lieu-local`. Không commit/push/rebase.

## Cách kiểm tra

Chạy web như thường lệ, mở câu trả lời có nguồn: không còn tiêu đề và các thẻ nguồn bên dưới; vẫn có thể bấm citation trong nội dung để xem đoạn nguồn, và vẫn có nút đánh giá.

## Kiểm tra thực tế

- `npm.cmd test`: 34/34 test đạt, gồm SSR xác nhận không còn danh sách nguồn, citation và feedback vẫn hiện, Markdown vẫn an toàn.
- `npm.cmd run build`: TypeScript và build production đạt.
- `npm.cmd run format:check`: đạt.
- `git diff --check`, UTF-8 và liên kết handover mới: đạt.
- Chưa kiểm tra trực quan trong trình duyệt ở lượt này; không gọi API thật hoặc LLM. Áp dụng nguyên theme sẵn có, không tạo hướng thiết kế mới cho thao tác gỡ một khối giao diện.

## Xử lý xung đột rebase

Người dùng chạy `git rebase develop` trên nhánh `docs/s2-tv4-nap-du-lieu-local`, nền `dfc0286`; commit `f5a9982` bị xung đột tại đầu danh sách `docs/handover/README.md`. Đã gộp cả liên kết handover TV4 ngày 05/11 và liên kết TV3 “Query web, excerpt và chẩn đoán 502” ngày 04/11, giữ nguyên nội dung của cả hai thành viên, rồi tiếp tục rebase. Không dùng skip hoặc chọn một phía để bỏ thay đổi bên kia.

Đã kiểm tra lại trên nội dung sau khi gộp: 34/34 test web, build TypeScript/Vite và format đều đạt. Không sửa thêm code backend/bot, không push hoặc force-push.
