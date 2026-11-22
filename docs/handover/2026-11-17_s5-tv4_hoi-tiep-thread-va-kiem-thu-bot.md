# TV4 · Hỏi tiếp trong thread và kiểm thử bot

Ngày 17/11/2026 (Asia/Saigon). Nhánh `feature/s5-tv4-hoi-tiep-thread-va-kiem-thu-bot`.
Phạm vi: ưu tiên 3 và 4 người dùng yêu cầu; bổ sung FR-BOT-04 của Sprint 4 và kiểm tra các lệnh Sprint 5.
Không tự commit, push hoặc mở/merge PR trong đợt này.

## Phạm vi và quyền sở hữu

Chỉ sửa `bot/` và bàn giao TV4. Không sửa backend, web, dữ liệu/pipeline TV2/TV3, planning, SRS hoặc README gốc.
Giữ ghi chú cũ. Các lệnh Sprint 5 `/setup`, `/clear`, mention và health đã được **agent TV1 làm hộ TV4** trước đó;
đợt này tích hợp Hỏi tiếp, kiểm thử hồi quy và đăng ký các lệnh, không nhận lại công của TV1.
Đã đọc `planning/sprint_plan.json`, `docs/02_SRS.md`, quy ước, AGENTS và hợp đồng/bàn giao liên quan.
Feedback bot FR-BOT-05 vẫn Deferred; không thêm nút 👍/👎, không phục hồi `/config`.

## File thay đổi và hành vi

- `bot/src/interactions/followup.ts`: xử lý nút, tạo/reuse thread, giới hạn bộ nhớ/thời gian, ngữ cảnh mở đầu và chống gửi đồng thời.
- `bot/src/commands/ask.ts`: thêm nút Hỏi tiếp bên cạnh link chia sẻ hiện có; dùng luồng thread chung cho `/ask` trong thread.
- `bot/src/handlers/message.ts`: thread do bot tạo nhận tin không cần mention hoặc `/setup`; kênh cha không tự được bật.
  Giữ sanitizer, rate limit, chia embed, timeout/thông báo lỗi và allowedMentions hiện có.
- `bot/src/index.ts`: định tuyến button interaction; thông báo cụ thể khi Discord từ chối Message Content Intent.
- `bot/src/commands/clear.ts`: sau `/clear all` thành công, hủy cache/nút/ngữ cảnh thread đang chờ của đúng server.
  Không hủy khi API thất bại hoặc người gõ không có quyền. Chặn cả race xóa trong lúc đang tạo thread.
- `bot/src/commands/help.ts`: hướng dẫn nút, ngữ cảnh công khai, hết hạn và khởi động lại.
- `bot/tests/followup.test.ts` (mới), `ask.test.ts`, `messageHandler.test.ts`, `guildCommands.test.ts`, `helpers.ts`:
  kiểm tra tích hợp handler với giả lập Discord/API, giữ các test trước đó.
- `bot/IMPLEMENTATION.md`: bổ sung hiện trạng và cách kiểm tra; `docs/handover/README.md`: thêm liên kết bàn giao.

## Quyết định và giới hạn

Backend kiểm tra `conversation_id` phải khớp `external_ref`, chưa có API fork. Không tái sử dụng hội thoại riêng của người hỏi
cho thread công khai, không thay hợp đồng API hoặc sửa code TV1. Thread mới có hội thoại riêng theo `discord:thread:<id>`;
lượt đầu nối trích đoạn **chỉ câu hỏi/câu trả lời công khai đang được chọn** vào `message`. Tối đa 500 ký tự câu hỏi và 900 ký tự
câu trả lời; cắt theo code point và tiếp tục thu ngắn để tổng request không vượt 2.000 ký tự. Lượt đầu quá dài để kèm ngữ cảnh
thì báo rút gọn, không gọi backend. Không gửi `conversation_id` kênh gốc hoặc sao chép các lượt lịch sử riêng.

Đây là ngữ cảnh mở đầu có giới hạn, **không phải sao chép đầy đủ hội thoại**. Ngữ cảnh là dữ liệu người dùng/AI, không được nâng
thành system prompt; lưu trong lượt hỏi bình thường nên cũng xuất hiện trong lịch sử/bản chia sẻ lượt đầu. Mock chỉ xác nhận
định tuyến/contract, chưa chứng minh chất lượng hiểu đại từ/ngữ cảnh bởi RAG thật. Nếu cần fork toàn bộ lịch sử, phối hợp TV1 riêng.

Một tin trả lời gốc chỉ tạo một thread (kể cả bấm đồng thời); nút gắn đúng server/kênh bằng mã UUID ngẫu nhiên.
Thread đã lưu trữ, bị khóa, không còn tồn tại hoặc không hoạt động một giờ không bị bot tự mở lại. Nút và phiên Hỏi tiếp
hết hạn tối đa 24 giờ tính từ khi tạo nút; Discord tự archive sau 60 phút không có hoạt động theo
[StartThreadOptions của discord.js](https://discord.js.org/docs/packages/discord.js/main/StartThreadOptions%3AInterface).
Một thread chỉ có một request đang xử lý; request chồng được báo đợi. Lỗi API giữ trích đoạn để người dùng chủ động thử lại;
không tự retry POST hoặc LLM.

Cache tối đa 500 nút và 500 thread, RAM của một tiến trình; loại mục cũ nhất khi đầy. Không lưu bền và không đảm bảo nút/ngữ cảnh
mở đầu sống qua restart. Sau restart, muốn hỏi trong thread dùng `/ask`, mention hoặc `/setup` kênh cha; backend vẫn quản lý lịch sử
theo external_ref. Bot không tự bật kênh cha hoặc cấp quyền Discord. Thread công khai tuân quyền xem của kênh cha.

## Kiểm tra đã chạy

- Đã viết test thất bại trước khi triển khai: thiếu module followup, thiếu nút trong `/ask`, handler bỏ qua thread chưa `/setup`;
  sau đó sửa để qua. Test race `/clear all` trong lúc tạo thread cũng đã bắt lỗi phục hồi cache, rồi được sửa.
- `npm.cmd run typecheck`: đạt. `npm.cmd test`: **75/75 test đạt**. `npm.cmd run format:check`: đạt.
  `git diff --check` đạt; kiểm UTF-8 và liên kết local của các tài liệu thay đổi không có lỗi.
- Backend local riêng ở `127.0.0.1:18000`, ép `CHAT_MODE=mock` cho tiến trình con, không sửa `.env` (vẫn cấu hình RAG).
  PostgreSQL/Qdrant/Redis hiện có healthy. Health API trả `ok`.
- Gọi qua API client thật tới **backend mock**: hai lượt cùng external_ref trả cùng conversation_id; thread khác trả ID khác;
  luồng followup nối ngữ cảnh và các lượt sau cùng ID riêng, không trộn với hội thoại gốc. Discord interaction trong smoke test này là giả lập.
- Tạo và đọc snapshot câu trả lời thành công bằng service token/header chia sẻ đúng contract. Một lần script kiểm tra ban đầu
  gọi nhầm token qua path trả 404; đã sửa script dùng `GET /answer-shares` + `X-Answer-Share-Token`, kiểm lại đạt.
  Chỉ dữ liệu giả, không đưa token hoặc snapshot vào Git/handover. Không cần thay endpoint backend.
- Discord REST ban đầu chỉ có `/ask`, `/ping`, `/help`, `/about`; đã chạy `npm.cmd run deploy-commands`, GET kiểm lại đủ
  `/about`, `/ask`, `/clear`, `/help`, `/ping`, `/setup` global. Không xóa hoặc thay cấu hình server test bằng API.
- Thử Gateway bằng entrypoint bot thật và client chẩn đoán tối giản đều nhận **`Used disallowed intents`**.
  Vì vậy **chưa chạy nghiệm thu slash interaction/mention/tạo thread thật**. Người dùng đã chọn bật Message Content Intent sau.
- Không chạy LLM, model, embedding, notebook hoặc RAG trả phí. Không chạy `/clear` xóa dữ liệu thật hoặc bật/tắt kênh thật để thử.
- Đã dừng tiến trình API mock sau kiểm tra, xác nhận cổng 18000 không còn listener; không để bot chạy ngầm.
  Các container hạ tầng có sẵn được giữ nguyên.

## Hướng dẫn nghiệm thu Discord sau khi bật intent

Trong Discord Developer Portal → Applications → Maidenless → Bot → Privileged Gateway Intents,
bật **Message Content Intent**, Save Changes. Bot cần View Channel, Send Messages, Read Message History,
Create Public Threads và Send Messages in Threads tại kênh test. Không cần Administrator.

Tại gốc dự án, mở Docker Desktop và chạy (các dependency phải được cài sẵn):

```powershell
make bot-check
make bot-dev
```

`make bot-dev` chạy API mock + bot, không sửa `.env`; không mở thêm bản API/bot khác trùng cổng.
Lệnh global đã đăng ký ngày 17/11; không cần deploy lại vì chỉ đổi handler/nội dung hướng dẫn.

1. `/ping`: có độ trễ Discord, API ổn; `/help`, `/about`: có hướng dẫn/nguồn/giấy phép.
2. `/ask question:Marika là ai?`: mock có câu trả lời, nguồn, nút **Hỏi tiếp** và link đầy đủ nếu WEB_URL truy cập được.
3. Bấm Hỏi tiếp, mở thread từ liên kết riêng. Gõ câu hỏi không mention; bot phải trả lời. Bấm nút cũ chỉ dẫn về cùng thread.
4. Tạo thread thứ hai từ một câu trả lời khác, thử không trộn các lượt. Hai thành viên trong cùng thread dùng chung ngữ cảnh.
   Với mock chỉ kiểm tra nhận/trả lời và phân luồng, không dùng để chấm chất lượng kiến thức.
5. Thử quyền thiếu Create Public Threads/Send Messages in Threads trên kênh test, thread bị khóa/lưu trữ và nút sau restart:
   phải báo thân thiện hoặc không nhận tin tự động sau restart theo giới hạn cache; không treo interaction.
6. Admin `/setup enable channel:#kênh-test`, gửi tin không mention, rồi `/setup disable channel:#kênh-test` để dọn.
   Người không có Manage Server không được gọi API thay đổi. `/setup disable-all` chỉ thử ở server test không có cấu hình cần giữ.
7. `/clear user`: chỉ xóa hội thoại riêng, thông báo giữ thread; chọn thành viên khác hoặc `/clear all` cần Manage Server.
   Chỉ thử `/clear all` ở server test sau khi đã xác nhận không cần giữ dữ liệu của server đó.
8. Mở link đầy đủ từ Discord: đúng toàn văn và nguồn, không mở toàn bộ hội thoại. Thiết bị đọc phải truy cập được WEB_URL/backend.

## Còn lại

Chưa tích hoàn tất nghiệm thu Discord thật, quyền tạo thread thực tế và chất lượng RAG trong thread. Chưa thử trình duyệt bấm link
trong đợt này (đã kiểm HTTP snapshot). Feedback bot Deferred; cấu hình spoiler theo guild/fork lịch sử đầy đủ không thuộc đợt này.

## Bổ sung: lỗi `/setup enable` sau khi người dùng bật intent (17/11/2026)

Người dùng gửi ảnh bot nhận lệnh nhưng trả “Không kết nối được dịch vụ”. Lần kiểm tra đầu không có listener cổng 18000,
health báo `ECONNREFUSED`; đã hướng dẫn bật cả API và bot. Ở lần gửi ảnh tiếp theo, API đã chạy, health 200 và cả ba
tài nguyên healthy, nhưng `GET /discord/guilds/{guild_id}/channels` trả **503 unavailable**. Vì vậy không tiếp tục
quy lỗi cho kết nối Discord hoặc cho rằng health 200 bảo đảm toàn bộ schema đã sẵn sàng.

`alembic current` cho thấy database local chỉ ở **0001**, còn `alembic heads` là **0005**. Đã đọc các migration
0002–0005: chúng bổ sung bảng/cột/index; `discord_guild_channels` của `/setup` nằm ở 0005. Đã chạy migration có sẵn
bằng `backend/.venv/Scripts/python.exe -X utf8 -m alembic upgrade head` từ `backend/`, xác nhận **0005 (head)**.
Không sửa migration, mã backend TV1, dữ liệu nguồn TV2/TV3, `.env` hay chế độ chat; không gọi model/LLM.

Kiểm tra sau sửa qua API client bot thật: health `ok`, đọc danh sách kênh thành công, bật một channel ID kiểm thử
trong guild ID giả riêng, đọc lại thấy cấu hình, tắt đúng channel kiểm thử và xác nhận danh sách trở về trạng thái ban đầu.
Không thao tác cấu hình server Discord thật, không chạy `/clear`, không xóa hội thoại hoặc corpus để thử. Bản ghi thử đã được dọn.
API đang chạy do người dùng mở được giữ nguyên; không mở thêm bản API/bot và không dừng tiến trình của người dùng.

Người dùng cần gửi **lệnh mới** `/setup enable channel:#kênh-test` trên Discord để xác nhận interaction thực tế;
ảnh lỗi cũ không tự cập nhật. Khi pull code có migration mới, chạy `make migrate` ở gốc dự án trước khi dùng tính năng mới.
Chưa ghi nhận `/setup` đã thành công trên Discord cho tới khi có kết quả mới của người dùng.
