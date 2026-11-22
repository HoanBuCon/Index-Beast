# Sửa review S5 TV1: quyền riêng tư và xóa tài khoản (mục 4, 5)

Nguồn: `2026-11-17_s5-tv2_ra-soat-ma-toan-he-thong.md`. Nhánh `fix/s5-tv1-review-privacy`.

## Đã sửa

- **#4 Đọc lịch sử ở chế độ memory.** `LiveChatService.stored_history` và `stored_has_message` ở chế độ memory nay áp cùng hợp đồng như PostgreSQL: hội thoại web cần `X-Conversation-Token` (so băm với `ConversationState.owner`, `hmac.compare_digest`) hoặc là tài khoản chủ (`ConversationState.user_id`); Discord chỉ service tin cậy; không có hội thoại thì 404, sai quyền thì 401. Hội thoại web mới ở chế độ memory được cấp token ngẫu nhiên (chỉ băm nằm trong RAM) và `ChatResponse.conversation_token` trả về cả ở chế độ memory (trước đây chỉ khi có repository).
- **#5 Xóa tài khoản.** `privacy.delete_account` giữ phiên tới bước cuối. Mỗi lô: xóa vector trước, xóa hàng sau. Bước cuối: chọn hội thoại còn sót, xóa vector, rồi MỘT transaction xóa hội thoại (kể cả cái mới xen vào), mọi phiên và dòng người dùng. Lỗi ở bất cứ bước nào để phiên còn hiệu lực nên `DELETE /me` gọi lại được; gọi lại khi đã xóa xong là no-op. Không thêm bảng. Vector của hội thoại tạo sát bước cuối: dọn best-effort sau commit, và `SemanticMemory.sync` dọn phần còn lại qua `conversation_exists` (`backend/app/rag/semantic_memory.py:173`, tồn tại, không cần D2 sửa).

## Quyết định

- Chỉ đọc lịch sử và kiểm tra đích feedback bị siết; lượt chat tiếp theo ở chế độ memory vẫn theo `conversation_id` như cũ (ngoài phạm vi mục 4). Hệ quả: mọi test/client memory đọc lịch sử phải gửi token.
- Vector của hội thoại tạo sau lần chọn cuối mà dọn lỗi chỉ ghi log (người dùng đã mất, retry không còn đường).

## Kiểm tra

- Test mới: `tests/unit/test_memory_history_auth.py` (7), `tests/unit/test_privacy_delete_account.py` (6, kho giả có rollback: lỗi SQL và Qdrant giữa lô, lỗi ở bước cuối, idempotent). Sửa `test_live_chat.py` (gửi token) và `tests/integration/test_privacy.py` (phiên còn sau lần xóa lỗi).
- `ruff check` sạch, `ruff format --check` sạch (286 file), `pytest tests/unit`: 965 passed, 20 skipped.

## Chưa kiểm chứng

- `tests/integration/test_privacy.py` chưa chạy: container Postgres trên máy thuộc dự án khác, không tạo DB tạm ở đó.
