# API server Discord cho bot (`/setup`, `/clear`) · TV1 → TV4

Bổ sung Sprint 5, ngày 16/11/2026. Hợp đồng đầy đủ nằm trong [`openapi.json`](openapi.json) (thẻ `discord-guild`);
file này giải thích cách bot dùng. Bot đã gọi các endpoint này từ Sprint 5 (lệnh `/setup enable|disable|disable-all`, `/clear user|all` và phần trả lời
trong kênh đã bật; xem handover `2026-11-16_s5-tv4_bot-lenh-co-ban.md`).

## Quy tắc chung

- Mọi endpoint nằm dưới `/api/v1/discord/guilds/{guild_id}` và **chỉ nhận `X-Service-Token`** (như `/answer-shares`).
  Thiếu hoặc sai token: `401 {code: "unauthorized"}`; `X-Admin-Token` không thay được. Lỗi luôn có dạng
  `{code, message, request_id}`.
- `guild_id`, `channel_id`: chuỗi số (Discord snowflake), 1–32 chữ số; sai định dạng thì `422 validation_error`
  (kiểm sau xác thực nên không dò được ID khi chưa có token).
- **Backend không kiểm tra quyền admin Discord.** Bot phải kiểm tra `ManageGuild`/`Administrator` của người gõ lệnh
  *trước khi* gọi `PUT/DELETE channels` và `memory/clear`; backend chỉ tin service token.
- Mọi thao tác ghi đều **idempotent** (gọi lại cho kết quả 200, số đếm 0). Không có `Idempotency-Key`; lỗi mạng thì cứ gọi lại.
- Lỗi hạ tầng (PostgreSQL, Qdrant): `503 unavailable`. Với `memory/clear` gọi lại sẽ hoàn tất phần còn lại.

## 1. Kênh bot tự trả lời (`/setup`)

| Lệnh | Gọi |
|---|---|
| `/setup #kênh` | `PUT /discord/guilds/{guild_id}/channels/{channel_id}` |
| `/setup disable #kênh` | `DELETE /discord/guilds/{guild_id}/channels/{channel_id}` |
| `/setup disable all` | `DELETE /discord/guilds/{guild_id}/channels` |
| Bot khởi động / nhận tin nhắn thường | `GET /discord/guilds/{guild_id}/channels` |

`GET` trả (sắp theo thời điểm bật):

```json
{
  "guild_id": "1000000000000000001",
  "channels": [{ "channel_id": "2000000000000000005", "enabled_at": "2026-11-16T03:04:05.123456Z" }],
  "limit": 50
}
```

`PUT` trả `200 {"channel_id": "...", "enabled_at": "..."}`; bật lại kênh đã bật trả đúng bản ghi cũ.
Tối đa **50 kênh/server**: kênh thứ 51 trả `409 {code: "conflict"}` (kênh đã bật vẫn `PUT` lại được).
`DELETE` (một kênh hoặc tất cả) trả `200 {"deleted": n}`; `n = 0` khi kênh chưa bật, không phải lỗi.

Gợi ý cho bot: bot là container không giữ trạng thái, nên `GET` danh sách một lần cho mỗi server rồi cache trong
RAM vài chục giây (và làm mới sau mỗi `/setup`) thay vì gọi cho mọi tin nhắn. Backend không có endpoint "kênh này bật chưa?"
riêng vì danh sách tối đa 50 phần tử. Bot chỉ cần xử lý tin nhắn ở kênh nằm trong danh sách, bỏ qua tin của bot khác.

## 2. Bot phải gửi `guild_id` trong `/chat`

Xóa ký ức theo server chỉ hoạt động trên hội thoại đã ghi `guild_id`. Từ Sprint 5, backend lưu `guild_id` của
`POST /chat` và `/chat/stream` **khi có service token hợp lệ** (không có token thì bị bỏ qua).
Bot cần thêm vào *mọi* request `/chat` của `/ask` và của kênh `/setup` (hiện `ask.ts` chưa gửi):

```ts
const response = await chat({
  message: question,
  channel: "discord",
  external_ref: externalRef,        // giữ nguyên công thức hiện tại
  guild_id: interaction.guildId!,   // chuỗi số; tin nhắn DM không có guildId thì bỏ trường này
  options: { lang: "auto", spoilers: true, web_search: "auto" },
});
```

`guild_id` cũng bật trần tần suất theo server (`RATE_LIMIT_GUILD_PER_MINUTE`, mặc định 30/phút).
Hội thoại cũ chưa có `guild_id` sẽ được gắn bổ sung ở lượt hỏi tiếp theo có gửi `guild_id`.

`external_ref` giữ nguyên: `discord:thread:<channelId>` trong thread, `discord:channel:<channelId>:<userHash>` ở nơi khác,
với `userHash = sha256(discordUserId)` dạng hex thường 64 ký tự (đúng công thức trong `ask.ts`).
Với tin nhắn trong kênh `/setup` (không phải thread) dùng cùng công thức để mỗi người một hội thoại riêng.

## 3. Xóa ký ức (`/clear`)

`POST /api/v1/discord/guilds/{guild_id}/memory/clear`, body là một trong hai dạng:

```json
{ "scope": "user", "user_hash": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08" }
```

```json
{ "scope": "all" }
```

`user_hash` = `sha256(discordUserId)` hex thường 64 ký tự, **bot tự băm**; backend không nhận ID người dùng thô và từ chối
giá trị không đúng dạng băm bằng `422`. Lưu ý: đây là **bút danh (pseudonym), không phải ẩn danh**: SHA-256 không muối của
một số công khai (snowflake) có thể bị đảo bằng cách băm lại danh sách ID thành viên đã biết. Cùng giá trị này đã nằm trong
`external_ref` của `/ask`. Muốn mạnh hơn cần HMAC với khóa bí mật chung bot-backend, tức phải sửa bot và migrate dữ liệu cũ
(rủi ro để TV1/TV4 quyết định). Ví dụ phản hồi `200`:

```json
{
  "guild_id": "1000000000000000001",
  "scope": "user",
  "conversations": 2,
  "threads_kept": 1,
  "vector_conversations": 2
}
```

| Trường | Ý nghĩa |
|---|---|
| `conversations` | Số hội thoại đã xóa. Tin nhắn, đánh giá, trạng thái và ký ức của chúng xóa theo (cascade) và **không** đếm riêng |
| `threads_kept` | `scope=user`: số hội thoại **thread** của server được giữ nguyên (thread dùng chung, không biết ai viết gì nên chỉ `/clear all` xóa). `scope=all`: luôn 0. Đây là mọi thread của server, không phải riêng của người đó |
| `vector_conversations` | Số hội thoại đã xóa điểm ký ức ở Qdrant (không phải số điểm); 0 khi không có kho vector |

Gọi lại ngay sau đó trả `200` với `conversations = 0` và `vector_conversations = 0` (`threads_kept` vẫn tính các thread còn lại).
**Bot phải nói rõ với người dùng khi `threads_kept > 0` sau `/clear @user`**, ví dụ "Đã xóa N cuộc hội thoại riêng; các
cuộc trò chuyện trong thread dùng chung chỉ bị xóa bằng `/clear all`". Nếu `conversations = 0` và `threads_kept = 0`, nói
là không có dữ liệu để xóa.

### Xóa những gì

Trong **đúng server `guild_id`** và chỉ hội thoại `channel = discord`:

| `scope` | Hội thoại bị xóa |
|---|---|
| `user` | Hội thoại có `external_ref` dạng `discord:channel:<kênh>:<user_hash>` (mọi kênh của server) |
| `all` | Mọi hội thoại Discord của server, **kể cả hội thoại thread** |

Với mỗi hội thoại xóa: các tin nhắn (kèm trace RAG và số đo), đánh giá 👍/👎, trạng thái làm việc (`conversation_runtime`),
ký ức dài hạn (`conversation_memories`) và các điểm vector tương ứng trong collection ký ức của Qdrant (xóa trước và sau
khi xóa PostgreSQL để một lượt lập chỉ mục chạy song song không để sót điểm; điểm mồ côi nếu còn chỉ chứa ID, không chứa
nội dung chat, và recall bỏ qua chúng).
**Không** xóa: cấu hình kênh `/setup` (dùng `DELETE channels` riêng), kho tri thức Elden Ring, link chia sẻ
`/answer-shares` đã tạo (snapshot Redis, tự hết hạn sau 24 giờ), hội thoại ở server khác hoặc trên web.

### Giới hạn đã biết

1. **Hội thoại tạo trước Sprint 5 có `guild_id = NULL`** nên `/clear` không thấy chúng. Chúng tự gắn `guild_id` khi người đó hỏi
   tiếp (nếu bot đã gửi `guild_id`); hội thoại không ai hỏi lại thì không xóa được qua API này. Hiện chưa có công cụ xóa theo ID người dùng cho dữ liệu cũ.
2. **Hội thoại thread dùng chung cho cả thread**, không gắn với một người, nên `/clear @user` **không** xóa chúng
   (chỉ `/clear all` xóa). Lệnh nên nói rõ điều này với người dùng.
3. Không xóa được tin nhắn Discord thật, chỉ xóa dữ liệu bot lưu.
4. Backend có một bản sao hội thoại trong RAM; `memory/clear` làm rỗng bản của worker xử lý lệnh. Nếu chạy nhiều worker API,
   worker khác còn giữ bản cũ sẽ nhận ra hội thoại đã bị xóa ở lượt hỏi kế tiếp và bắt đầu lại một hội thoại rỗng ngay
   trong lượt đó (như lần hỏi đầu tiên); bot không thấy lỗi. Dữ liệu đã xóa không bao giờ được khôi phục.
5. Một lượt `/chat` đang chạy đồng thời với `/clear` có thể ghi lại hội thoại mới ngay sau khi xóa.

## Mã lỗi

| Mã | `code` | Khi nào |
|---|---|---|
| 401 | `unauthorized` | Thiếu/sai `X-Service-Token` |
| 409 | `conflict` | `PUT channels` khi server đã đủ 50 kênh |
| 422 | `validation_error` | ID không phải chuỗi số ≤ 32 ký tự; `scope` sai; `user_hash` không phải 64 ký tự hex thường |
| 503 | `unavailable` | PostgreSQL/Qdrant lỗi (an toàn khi gọi lại) |

429 không áp dụng cho các endpoint này (chỉ `/chat`).
