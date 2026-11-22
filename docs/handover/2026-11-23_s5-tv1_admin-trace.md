# TV1 · Trang admin: tra cứu trace từ hội thoại, danh sách cuộn, sao chép JSON (23/11/2026)

Sprint 5, nhánh `feat/s5-tv1-google-auth-trace-sidebar`.

## Nguyên nhân

- "Hội thoại gần đây" (`/admin/stats`) hiện **id hội thoại**, còn `GET /admin/trace/{id}` tra theo **id tin nhắn assistant** (`MemoryRepository.trace` chỉ tìm `Message.id`, rồi loại tin không phải assistant). Dán id hội thoại vào "Tra cứu trace" nên ra 404 "Không tìm thấy hội thoại hoặc chức năng API...". Id ở "Phản hồi chưa hữu ích" là `message_id` nên chạy.
- Hai danh sách dài bằng cả trang, khung JSON không chọn riêng được (Ctrl+A chọn cả trang) và không có nút sao chép.

## Thay đổi

Backend
1. `core/db/repositories.py` `recent_conversations`: thêm phần tử thứ 4, id câu trả lời assistant cuối (subquery tương quan sắp `created_at desc, id desc`, một câu SQL, không N+1); `None` nếu chưa có.
2. `app/api/schemas/admin.py` + `routes/admin.py`: `AdminConversation.last_message_id` (nullable, bỏ khỏi JSON khi null vì client web từ chối null ở trường tùy chọn).
3. `MemoryRepository.trace(id)`: không có tin nhắn với id đó thì xem id là id hội thoại và lấy câu trả lời assistant cuối. Không có gì thì vẫn `None` rồi 404. Quy tắc xác thực `/admin/*` giữ nguyên.
4. `LiveChatService.trace` (chế độ không DB): nếu id là hội thoại trong RAM thì dùng câu trả lời assistant cuối còn trace.
5. Mô tả endpoint trace nêu việc nhận id hội thoại.

Web
- `src/components/admin/AdminLists.tsx` (mới): `ConversationList`, `FeedbackList`, `TraceViewer`, `traceTargetOf`.
- `src/lib/adminTrace.ts` (mới): `isSelectAllKey`, `selectOnly`, `copyText`.
- "Hội thoại gần đây" hiện Message ID (câu trả lời cuối) và id hội thoại, nút "Xem trace" mỗi dòng (điền ô tra cứu và tải ngay). "Phản hồi chưa hữu ích" cũng có nút đó. Cả hai nằm trong `div.admin-scroll` (`max-height: 22rem`, `overflow-y: auto`, `tabIndex=0`, `role="region"`, `aria-label`).
- Khung JSON: `<pre>` focus được, Ctrl/Cmd+A chỉ chọn nội dung khung (preventDefault), nút "Sao chép" dùng `navigator.clipboard.writeText`, hiện "Đã sao chép" 3 giây; clipboard lỗi thì hiện hướng dẫn chọn thủ công.
- `AdminStats.conversations[].last_message_id?` trong `types.ts`, kiểm trong `getAdminStats`; `load(kinds, traceId)` nhận id trực tiếp.

## Quyết định

- Fallback đặt ở tầng repository/service, không ở route, để dùng chung với `scripts/trace.py` và giữ một chỗ xử lý lỗi DB.
- Nút trên dòng hội thoại gửi `last_message_id`, nếu chưa có thì gửi id hội thoại (backend nay chấp nhận, rồi trả 404 nếu hội thoại chưa có câu trả lời).
- Hàm chọn/sao chép tách ra `lib/adminTrace.ts` để test không cần DOM.

## Kiểm tra

| Lệnh | Kết quả |
|---|---|
| `pytest tests/unit/test_admin_trace_lookup.py tests/unit/test_trace.py` | 28 passed (test viết trước, thấy fail trước khi sửa) |
| `ruff check`, `ruff format --check` | đạt (298 file) |
| `pytest tests/unit` | 1082 passed, 3 failed ngoài phạm vi (xem dưới) |
| web `npm run typecheck`, `npm test`, `npx prettier --check .` | đạt; 101 test pass |

3 test lỗi thuộc phần của agent khác đang làm dở (`test_env_example`, `test_google_auth`, `test_web_search`), không đụng file admin.

## Chưa làm / chưa kiểm

- Chưa chạy test tích hợp Postgres (SQLite biên dịch SQL repository trong test đơn vị); `test_admin_stats.py` tích hợp vẫn đọc tuple theo chỉ số nên không đổi.
- Chưa xem trực quan trên trình duyệt (chỉ SSR + test hàm thuần); Ctrl+A thật cần thử tay.
- `docs/api/openapi.json` chưa sinh lại (lead làm).
