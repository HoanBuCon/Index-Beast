# TV1 · Xóa từng hội thoại của tài khoản: sửa hội thoại "dính" ở mục "Của tài khoản" (22/11/2026)

Sprint 5. Nhánh `fix/s5-tv1-delete-account-conversation`.

## Lỗi

Trên production, sidebar web của tài khoản đã đăng nhập có hai mục "Elden Ring là gì?" ở "Của tài khoản" không xóa được.

Nguyên nhân:
- Nút × ở mục "Tất cả" chỉ gọi `history.remove` (xóa bản lưu trong trình duyệt). Hội thoại đã gắn với tài khoản vẫn còn trên server.
- Mục "Của tài khoản" liệt kê hội thoại trên server chưa có bản trong trình duyệt (`remoteOnly` trong `ChatPage.tsx`). Hội thoại vừa xóa ở "Tất cả" vì thế hiện lại ở đây.
- Mục này không có nút xóa, và backend không có API xóa một hội thoại (chỉ có `DELETE /me` xóa cả tài khoản).

## Thay đổi

- **Backend**
  - `privacy.delete_conversation` (`app/services/privacy.py`): chỉ xóa khi hội thoại thuộc `user_id`; không tồn tại hoặc của người khác đều 404 như nhau. Xóa vector ký ức trong Qdrant trước, hàng PostgreSQL sau (tin nhắn, feedback, ký ức đi theo `ON DELETE CASCADE`). Lỗi Qdrant giữ nguyên hàng để xóa lại được.
  - `DELETE /api/v1/me/conversations/{conversation_id}` (`app/api/routes/auth.py`): cần cookie phiên và cùng Origin như `DELETE /me`, trả 204. Bỏ hội thoại khỏi bộ nhớ RAM của chat service (`forget`) để lượt hỏi sau không dùng lại bản cũ.
- **Web**
  - `deleteMyConversation(id)` (`src/api/auth.ts`): 204 hoặc 404 (đã xóa ở thiết bị khác) là xong; id không phải UUID thì không gửi.
  - `useAuth`: thêm `forgetConversation(id)` để bỏ hội thoại khỏi danh sách "Của tài khoản".
  - `ChatPage.tsx`: mục "Của tài khoản" có nút ×. Nút × ở mục "Tất cả" xóa cả bản trên server nếu hội thoại thuộc tài khoản đang đăng nhập (`ownerUserId` hoặc `serverId` nằm trong danh sách tài khoản). Server lỗi thì giữ nguyên bản trong trình duyệt và báo "Không xóa được hội thoại trên tài khoản". Hội thoại của khách vẫn chỉ xóa trong trình duyệt như cũ.

## Kiểm tra

| Lệnh | Kết quả |
|---|---|
| `pytest tests/unit` (6 test mới: 3 cho `delete_conversation`, 3 cho route; viết trước và thất bại trước khi sửa) | 1044 passed |
| `ruff check`, `ruff format --check` | đạt |
| web `npm run typecheck`, `npm test` (2 test mới), `prettier --check` | sạch, 85/85, sạch |

## Chưa làm

- Chưa deploy và chưa thử trên trình duyệt thật.
- Xóa không hỏi xác nhận, giống nút × trước đây; xóa trên server là vĩnh viễn.
- Hội thoại khách (chưa nhận về tài khoản) vẫn chỉ xóa trong trình duyệt; bản trên server được retention 90 ngày dọn.
