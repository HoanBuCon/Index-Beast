# TV4 · Bot Sprint 5: lệnh cơ bản, `/setup`, `/clear`, trả lời mention

Ngày 16/11/2026, nhánh `feature/s5-bot-lenh-co-ban` (tách từ `feature/s5-tv1-discord-guild-api`, PR #110 chưa merge, nên cần merge #110 trước).
**Phần này do agent của TV1 làm hộ TV4**; chưa push, chưa mở PR. Chỉ sửa `bot/` và tài liệu; không sửa backend.

## Phạm vi (FR-BOT-07..10)

| Lệnh / hành vi | Cách dùng |
|---|---|
| `/help` | Liệt kê mọi lệnh (đồng bộ registry, có test) |
| `/about` | Thêm nhóm 4 Hollows (Quỷ Tháng 5 Khóc – Tech Lead, Himmel – dữ liệu, Thợ Săn Lợn Sang – RAG/AI, Riley – web/bot); giữ nguồn CC BY-SA và tuyên bố fan project |
| `/ping` | Độ trễ websocket Discord + vòng đi về `GET /api/v1/health` (ok / suy giảm kèm tên tài nguyên lỗi / không truy cập được); trả lời riêng tư |
| `/setup enable channel:#kênh` | Bật kênh (text/announcement) cho bot trả lời mọi tin nhắn |
| `/setup disable channel:#kênh` | Tắt một kênh |
| `/setup disable-all` | Tắt mọi kênh của server |
| `/clear user [member:@ai]` | Xóa ký ức của chính mình (mặc định) hoặc của người khác (cần Manage Server) |
| `/clear all` | Xóa ký ức cả server kể cả thread (cần Manage Server) |
| `/ask` | Gửi thêm `guild_id` (bỏ trường khi DM) |
| Mention `@bot câu hỏi` | Trả lời ở mọi kênh bot xem được; reply vào tin của bot (có ping) cũng tính là mention |
| Kênh `/setup` | Trả lời mọi tin nhắn; thread con của kênh đã bật dùng chung trạng thái bật |

## Quyết định

1. **Subcommand thay cho văn bản tự do**: Discord không cho gõ `/setup disable all` đúng nghĩa đen, nên dùng `enable | disable | disable-all`.
   `/clear @user` thành `/clear user [member]` vì `user` là subcommand và `member` tùy chọn (bỏ trống = chính mình), còn `/clear all` riêng.
2. **Quyền**: `Manage Server` (`PermissionFlagsBits.ManageGuild`; Administrator tự có). `/setup` còn đặt `default_member_permissions` và chỉ trong server
   (`setContexts(Guild)`), nhưng handler vẫn kiểm lại vì admin server có thể đổi quyền hiển thị. Kiểm trước khi gọi API; backend không kiểm.
3. **`/clear user`**: người dùng thường chỉ xóa được của mình; bot bị từ chối (không có ký ức). Kết quả hiển thị số hội thoại đã xóa; nếu `threads_kept > 0`
   nói rõ thread chỉ bị xóa bằng `/clear all`; nếu không có gì thì nói không có dữ liệu. Hash người dùng dùng chung `utils/identity.ts` với `/ask` (công thức không đổi).
4. **Cache kênh** (`utils/guildChannelCache.ts`): GET danh sách kênh 1 lần/server, TTL 30 giây, gộp các lần tải đồng thời; API lỗi thì dùng bản cũ
   nếu có, chưa có thì bỏ qua tin nhắn (không trả lời, ghi log). `/setup` gọi `invalidate` kể cả khi lỗi (có thể backend đã ghi trước khi mạng đứt).
5. **Giới hạn tần suất** (`utils/rateLimit.ts`): 5 tin/phút/người trong RAM; vượt thì nhắc **một lần** mỗi cửa sổ rồi im lặng (tránh bot tự spam).
   Backend vẫn có trần riêng theo server (`RATE_LIMIT_GUILD_PER_MINUTE`).
6. **An toàn trả lời**: bỏ qua bot, webhook, tin hệ thống, DM; tin trống bị bỏ; `@everyone`/role không tính là mention bot; mọi phản hồi dùng
   `allowedMentions: { parse: [] }` (và `repliedUser: false`). Tin dài hơn 2000 ký tự ở kênh tự trả lời bị bỏ qua (thường là chat thường), chỉ báo khi mention.
7. **`config.ts` đã xóa** (stub không đăng ký): `/setup` thay thế phần "kênh được phép". Chế độ spoiler theo server (phần còn lại của FR-BOT-07) chưa làm.
8. Không thêm `/feedback` hay `/source`: không rẻ (feedback đã gỡ khỏi bot, xem TBD-09).
9. Trả lời tin nhắn không tạo nút "xem đầy đủ trên web" (chỉ `/ask` có); thêm sau nếu cần.

## Việc phải làm khi triển khai

- **Bật Message Content Intent** trong Discord Developer Portal (Bot → Privileged Gateway Intents). Chưa bật thì `client.login` lỗi `Used disallowed intents`
  và bot không lên. Bot ở trên 100 server còn cần Discord duyệt intent này.
- Chạy lại `npm run deploy-commands` (hoặc `make bot-deploy`) để đăng ký `/setup`, `/clear` và định nghĩa `/ping` mới; lệnh toàn cục có thể mất vài phút để hiện.
- Cần `API_SERVICE_TOKEN` khớp backend: các endpoint guild chỉ nhận service token, và backend bỏ `guild_id` của `/chat` nếu không có token.
- Bot cần quyền xem kênh và gửi tin nhắn ở kênh được bật (bot không tự kiểm tra khi `/setup`).

## Kiểm tra (trong `bot/`, Node và npm của máy này, `npm ci` sạch)

- `npm run typecheck`: sạch.
- `npm test`: **59 test pass, 0 fail**; thêm `guildApi.test.ts`, `guildCommands.test.ts`, `messageHandler.test.ts`, cập nhật `ask`, `bot`, `info`).
  Bao phủ: đường dẫn/phương thức/token của client guild, `clearMemory` và kiểm tra dữ liệu, 409, `health` 200/503/lỗi, cache (TTL, gộp tải, bản cũ khi lỗi, invalidate),
  rate limit, `/setup` (quyền, ánh xạ API, làm mới cache, ẩn lỗi thô), `/clear` (tự xóa, quyền, `threads_kept`, DM, bot), `/ping`, `/help` có đủ mọi lệnh trong registry,
  `/ask` gửi `guild_id`, handler tin nhắn (kênh bật, mention, thread, bot/webhook/system/DM, rate limit, tin dài, lỗi API, tin dài chia nhiều tin, không ping).
- `npm run format:check`: sạch. Repo bot không có script `lint` hay `build` riêng; `typecheck` và `format:check` thay thế.

## Chưa kiểm chứng

- Chưa chạy với Discord thật hay backend thật: mọi thứ qua interaction/message/fetch giả. Chưa thử Message Content Intent trên Developer Portal,
  quyền `default_member_permissions` hiển thị trong client, chọn kênh trong `/setup` và hành vi reply-to-bot.
- Tích hợp với #110 (hình dạng JSON endpoint guild) chỉ dựa vào hợp đồng và OpenAPI; chưa gọi API thật.
- Cache theo tiến trình: nếu chạy nhiều bản bot, thay đổi `/setup` ở bản này tới bản kia tối đa 30 giây.
- Rate limit trong RAM, mất khi bot khởi động lại.

## Cần TV1/TV4 quyết định

- Giữ 5 tin/phút/người và TTL 30 giây hay đổi.
- Có muốn mention trong kênh chưa bật `/setup` (hiện cho phép mọi kênh) chỉ hoạt động ở kênh đã bật không.
- FR-BOT-07: bỏ phần "chế độ spoiler theo server" hay làm sau.
