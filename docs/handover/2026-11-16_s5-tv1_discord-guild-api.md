# TV1 · API server Discord cho bot: kênh `/setup` và xóa ký ức `/clear`

Ngày 16/11/2026, nhánh `feature/s5-tv1-discord-guild-api` (tách từ `origin/develop` tại `3719e02`). Chưa push, chưa mở PR.
Phần bot (lệnh, kiểm quyền admin, gọi API) do TV4 làm theo [hợp đồng](../api/discord-guild-tv4.md); TV1 không sửa `bot/`.

## Phạm vi

- Migration `0005`: bảng `discord_guild_channels (guild_id, channel_id, created_at)`, khóa chính kép; chỉ mục `ix_conversations_guild_id`.
  Cột `conversations.guild_id` **đã có từ `0001`** nhưng chưa từng được ghi, nên không thêm cột mới.
- Endpoint dưới `/api/v1/discord/guilds/{guild_id}`, chỉ nhận `X-Service-Token` (401 nếu thiếu/sai, kể cả khi gửi `X-Admin-Token`):
  `GET channels`, `PUT channels/{channel_id}`, `DELETE channels/{channel_id}`, `DELETE channels`, `POST memory/clear`
  (`{scope:"user", user_hash}` hoặc `{scope:"all"}`).
- `/chat` và `/chat/stream` ghi `conversations.guild_id` khi `guild_id` đến cùng service token hợp lệ; không có token thì `guild_id`
  bị bỏ (trước đây chỉ bị bỏ khi tính rate limit).
- OpenAPI tái sinh bằng `python -m scripts.export_openapi` (+510 dòng, `--check` đạt); SRS lên 0.8.2 (FR-BOT-09, FR-BOT-10, §5.1, §6).

## Quyết định

1. **Xóa theo người dùng dựa vào `external_ref`**: hội thoại cá nhân có `external_ref = discord:channel:<kênh>:<sha256(userId)>`
   (công thức sẵn có của bot), nên `/clear @user` lọc `guild_id` + `external_ref` kết thúc bằng `:<user_hash>`. Không thêm cột người dùng.
   Bot tự băm; backend không nhận ID người dùng thô (NFR-PRIV-01) và từ chối giá trị không phải 64 ký tự hex thường.
   So khớp dùng `startswith/endswith` có escape, không dùng `LIKE` thô.
2. **Hội thoại thread (`discord:thread:<id>`) dùng chung nhiều người** nên không gắn được với một người: `/clear @user` không xóa,
   chỉ `/clear all` xóa. Hội thoại có `guild_id = NULL` (tạo trước Sprint 5) không bị `/clear` chạm tới; chúng tự gắn `guild_id`
   ở lượt hỏi tiếp theo có `guild_id` (không ghi đè nếu đã có).
3. **Thứ tự xóa**: điểm vector trong Qdrant (lọc theo payload `conversation_id`, gồm cả điểm mồ côi) trước, dòng PostgreSQL sau, theo lô 500 hội thoại.
   Qdrant lỗi thì PostgreSQL chưa bị xóa → 503, gọi lại hoàn tất. Mọi bảng con xóa bằng `ON DELETE CASCADE` (messages gồm trace RAG, feedback,
   conversation_runtime, conversation_memories). Trả số đếm `conversations, messages, feedback, memories, vector_points`; gọi lại trả 0.
4. **Trần 50 kênh/server** (`MAX_CHANNELS_PER_GUILD`, hằng số, chưa đưa vào cấu hình vì `core/config.py` đang bị khóa); kiểm trong transaction có
   `pg_advisory_xact_lock` theo server để hai `/setup` đồng thời không vượt trần. Vượt trần: `409 conflict` (thêm `ConflictError` vào `core/errors.py`).
5. **Một chút chạm vào `chat.py`** (cho phép trong yêu cầu): truyền `guild_id` vào `Snapshot`, thêm `LiveChatService.forget()` để bỏ bản hội thoại
   trong RAM sau khi xóa, và `_refresh` bỏ bản RAM cũ + trả 503 "gửi lại" nếu hội thoại đã bị xóa bởi worker khác.
   `Snapshot` chỉ thêm trường tùy chọn (GitNexus: 6 caller trực tiếp, không đổi chữ ký); `enforce_chat_limits`: 2 caller (`/chat`, `/chat/stream`).
6. Cấu hình `/setup` lưu PostgreSQL, **không** bị `/clear` xóa. Không thêm endpoint "kênh này bật chưa?": danh sách ≤ 50, bot cache.

## Kiểm tra

Chạy trong `backend/` với venv mới tạo (Python 3.11.9, `requirements-dev.txt` + `constraints.txt`):

- `ruff check .` và `ruff format --check .`: sạch (278 file đã đúng định dạng).
- `pytest tests/unit -q`: **1175 passed, 20 skipped**, 0 lỗi; không có lỗi môi trường cục bộ nào phải loại trừ. File mới
  `tests/unit/test_discord_guild_api.py` có 34 test: 401 cho cả 5 endpoint × 3 kiểu thiếu/sai token, ID sai (xác thực trước, rồi 422), roundtrip
  idempotent, trần 409, 503, `scope`/`user_hash` sai (không echo giá trị gửi lên), lọc Qdrant theo `conversation_id`, `forget`, bản RAM cũ, và
  `guild_id` chỉ tới service khi có token.
- `python -m scripts.export_openapi --check`: đạt.
- Test tích hợp mới `tests/integration/test_discord_guild.py` (10 test: kênh idempotent/theo server, trần dưới 60 `enable` đồng thời, `save` ghi và gắn bổ sung
  `guild_id`, `/clear` theo người/cả server/idempotent/ký tự đại diện/Qdrant lỗi, cấu hình kênh còn sau `/clear`) và kiểm migration-so-với-model có sẵn
  trong `test_db_schema.py` (tự bao phủ `0005`, cả downgrade → upgrade).

## Chưa kiểm chứng

- **Test tích hợp chưa chạy** (10 test bị `-m "not integration"` loại; máy này không có Docker/PostgreSQL). Chỉ kiểm được cú pháp, ruff và biên dịch SQL sang dialect
  PostgreSQL. Cần CI (`pytest -m integration`) xác nhận, đặc biệt `pg_advisory_xact_lock(hashtextextended(...))`, đếm theo lô và cascade.
- Chưa thử với Qdrant server thật: bộ đếm/xóa theo `MatchAny` chỉ kiểm bằng client giả; Qdrant local (in-memory) bỏ qua payload index.
- Chưa thử với bot hay Discord thật; bot hiện chưa gửi `guild_id`.
- Nhiều worker API: bản RAM chỉ được xóa ở worker xử lý `/clear`; worker khác tự dọn ở lượt tiếp theo (503 một lần), chưa thử với 2 worker thật.
- Không có cơ chế dọn dữ liệu cũ (`guild_id = NULL`) và chưa có chính sách xóa 90 ngày của NFR-PRIV-01.

## Cần TV1 xác nhận

- Chấp nhận `/clear @user` không xóa hội thoại thread; hay muốn lưu thêm băm người dùng theo từng tin nhắn để xóa chính xác (cần migration/thay đổi lớn hơn)?
- Đường dẫn `POST .../memory/clear` (thay vì `DELETE ... memory` có body) và trần 50 kênh có ổn không.
- Có cần nút/endpoint admin xóa dữ liệu `guild_id = NULL` theo người dùng không.
