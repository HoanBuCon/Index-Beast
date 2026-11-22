# TV1 · Hạn mức hỏi đáp mỗi ngày (22/11/2026)

Sprint 5, sau sự cố chống DoS. Nhánh `feat/s5-tv1-chat-quota`. Runbook: [`docs/production.md`](../production.md) mục 7c.

## Sự cố

- 22/11/2026: một IP lạ nhận **234 câu trả lời thật**: ~2,34 triệu token prompt, 112 nghìn token completion, 115 lượt tìm corpus (có Jina rerank), 10 lượt Tavily.
- Giới hạn mỗi phút (`RATE_LIMIT_PER_MINUTE`=10) không chặn được người hỏi đều đặn, chậm: mỗi câu đều hợp lệ, nhưng tổng trong ngày tốn tiền.

## Thay đổi

1. **`app/services/quota.py`** (`ChatQuota`): đếm trong Redis `quota:questions:<khóa>:<ngày>` và `quota:tokens:<khóa>:<ngày>` (+ `quota:tokens:global:<ngày>`), ngày theo giờ Việt Nam, TTL 2 ngày. `reserve` kiểm trước khi gọi LLM, `charge` cộng token sau khi trả lời.
2. **`app/api/guard.py`**: `enforce_chat_limits(request, body, user)`. Thứ tự: kiểm kênh discord/service token, mock thoát sớm, **admin thoát hẳn** (không giới hạn phút, không hạn mức), giới hạn mỗi phút như cũ, rồi `reserve` với khóa `bot:<external_ref>`, `user:<id>` hoặc `guest:<ip>`; khóa gắn vào request (`ChatRequest.attach_quota`).
3. **`LiveChatService`**: thuộc tính `usage_sink`; `_save` tính token từ trace (cả khi không có DB) và gọi sink sau khi lượt được lưu, không gọi ở đường trả lại lượt trùng. Cả JSON lẫn stream đều qua `_save`. Sink lỗi chỉ ghi log. `main.py` gắn `ChatQuota(...).charge` lúc khởi động.
4. **Lỗi**: `QuotaExceededError` (429, `code=quota_exceeded`, `Retry-After` = số giây đến 0 giờ VN); `rate_limited` giữ cho giới hạn mỗi phút.
5. **Cấu hình**: `CHAT_GUEST_DAILY_QUESTIONS`=5, `CHAT_USER_DAILY_QUESTIONS`=30, `CHAT_GUEST_DAILY_TOKENS`=100000, `CHAT_USER_DAILY_TOKENS`=500000, `CHAT_DAILY_TOKEN_BUDGET`=5000000 (0 = tắt) trong `core/config.py`, `.env.example`, `docker-compose.yml`, nhắc trong `.env.prod.example`.
6. Docs: `production.md` 7c, `privacy.md`, `02_SRS.md` (FR-CHAT-07).

## Quyết định

- Câu hỏi được tính khi nhận, kể cả khi trả lời lỗi sau đó: chặn được kẻ cố tình gây lỗi để dò. Token chỉ tính khi lượt được lưu, nên ngân sách có thể vượt tối đa một câu.
- Redis lỗi thì từ chối (503), cùng nguyên tắc với giới hạn mỗi phút: mỗi câu tốn tiền LLM.
- Admin dựa vào `AuthUser.is_admin` (`AUTH_ADMIN_DISCORD_IDS`).
- Chế độ mock không có hạn mức.

## Kiểm tra

| Lệnh | Kết quả |
|---|---|
| `pytest tests/unit/test_chat_quota.py` | 14 passed (12 mô tả hành vi viết trước, thêm test đường stream và sink lỗi) |
| `pytest tests/unit` | 1038 passed |
| `ruff check`, `ruff format --check` | đạt |

## Chưa làm

- Người dùng bot không có hạn mức riêng từng người (bot chỉ gửi ref thread/kênh): chỉ bị giới hạn mỗi phút và tính vào ngân sách chung.
- Câu hỏi tính khi nhận dù câu trả lời lỗi sau đó.
- Token chỉ được ghi sau khi lượt hỏi lưu xong: câu trả lời lỗi hoặc stream bị client ngắt giữa chừng đã tốn token LLM nhưng không bị trừ vào ngân sách. Trần số câu hỏi (tính khi nhận) vẫn chặn được kiểu lạm dụng này.
- Web và bot đã hiện thông báo `quota_exceeded` của server (web: không nối "Thử lại sau"; bot: bỏ qua thông báo dài quá 500 ký tự).
- Chưa deploy.
