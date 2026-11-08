# TV4 · Bot Sprint 2: API client và `/ask`

Ghi chú Sprint 2 bên dưới được giữ để truy vết. Xem phần **Bot TV4 · Sprint 3** cuối file để biết cập nhật ngày 08/11/2026;
các mục chia câu trả lời và `/help`/`/about` đã có code ở Sprint 3, còn nghiệm thu Discord thật và link đọc đầy đủ trên web chưa hoàn tất.

Mã phía bot đã có kiểm thử độc lập bằng dữ liệu giả. **Chưa nghiệm thu tích hợp Discord → backend thật**, không đồng nghĩa đã đăng ký `/ask` trên Discord.

## Phạm vi

- Types viết tay theo `docs/api/openapi.json`, thích nghi phần hợp đồng công khai đã có trong web; không import mã UI hay sinh lại OpenAPI.
- Client `createApiClient()` có `chat`, `chatStream`, `sendFeedback`, `getConversation`; timeout mặc định 60 giây (lớn hơn hạn 45 giây `CHAT_TIMEOUT_SECONDS` của backend), `X-Request-ID`, service token tùy chọn, kiểm tra dữ liệu trả về, lỗi thân thiện và giữ `Retry-After` khi 429.
- `/ask question`: defer trước I/O, gọi JSON `/api/v1/chat` với `channel=discord`, trả embed có nguồn. Không gửi raw user ID trong `external_ref`; dùng SHA-256 cho phần user.
- Câu trả lời/nguồn dài được rút gọn để vừa một embed, có ghi chú. Không tạo link “xem đầy đủ” giả vì route hội thoại công khai chưa được tích hợp.
- Đăng ký trong registry cùng `/ping`; script deploy hiện có vẫn đăng ký global theo yêu cầu trước đó.

Giữ chú thích khung ban đầu. Các ghi chú về feedback/hỏi tiếp/chia câu trả lời của S3–S4 không có nghĩa các tính năng đó đã được triển khai trong lệnh `/ask`.

## Kiểm tra không cần thành viên khác

Ở **gốc dự án**, có thể chạy cả ba kiểm tra bằng:

```powershell
make bot-check
```

Makefile dùng `npm.cmd` trên Windows, `npm` trên Linux/macOS. Lần đầu vẫn cần cài dependency với `cd bot` rồi `npm.cmd ci` (Linux/macOS: `npm ci`).

Chạy từ `bot/`:

```powershell
npm.cmd run typecheck
npm.cmd test
npm.cmd run format:check
```

21 test gồm 2 test S1 và 19 test mới: cấu hình, contract, JSON/SSE, UUID request ID, timeout kể cả đọc body, hủy, lỗi 401/403/404/422/429/500, validation, feedback, hội thoại, thứ tự defer/API, nguồn, giới hạn embed và không lộ lỗi thô. Test không đọc `.env`, không mở mạng hoặc gọi Discord/LLM.

## Cấu hình đã có

Không cần sửa `.env.example` hoặc Docker Compose cho bước này.

- `DISCORD_TOKEN`: bắt buộc, không ghi vào tài liệu/log. `DISCORD_CLIENT_ID`, `DISCORD_GUILD_ID`: không bắt buộc; thiếu Application ID thì `deploy-commands` lấy từ `GET /applications/@me` bằng token.
- `BOT_API_URL`: để trống khi chạy bot trên máy → `http://127.0.0.1:<API_PORT>`; `API_PORT` mặc định 18000. Chấp nhận URL gốc hoặc kết thúc `/api/v1`, không ghép tiền tố hai lần.
- Trong container, Compose hiện đặt `BOT_API_URL=http://api:18000`; `api` là tên service, không phải localhost của máy.
- `API_SERVICE_TOKEN`: gửi `X-Service-Token` nếu được cấu hình khác `change-me`. Theo bàn giao TV1, xác thực service token thuộc S4; client không tự thêm yêu cầu bảo mật vào backend.
- API timeout 60 giây; không tự retry POST để tránh gửi câu hỏi hai lần.

Client không ép backend sang mock. Backend có thể đang ở mode `rag`/`llm_only`; chỉ dùng môi trường mock của TV1 khi nghiệm thu Sprint 2, tránh vô tình gọi LLM trả phí. Không tự sửa mode hoặc `.env` của thành viên khác.

## Khi sẵn sàng kiểm thử tích hợp

Để chạy bằng **một lệnh**: mở Docker Desktop trước, rồi tại gốc repo chạy:

```powershell
make bot-dev
```

Lệnh chờ PostgreSQL/Redis/Qdrant healthy rồi chạy API mock và bot song song trong cùng terminal. Tự truyền `CHAT_MODE=mock` và địa chỉ API localhost đúng `API_PORT` cho tiến trình con, không sửa `.env`. Chờ cả `Application startup complete` và `Bot đã online.` trước khi gửi `/ask`. Giữ terminal mở; Ctrl+C dừng API/bot, hạ tầng Docker vẫn chạy và giữ dữ liệu.

Cần dependency backend/bot đã cài và cấu hình Discord hợp lệ. Nếu API hoặc bot đã chạy ở terminal khác, dừng bản đó trước để tránh trùng cổng/đăng nhập bot hai lần. Lệnh không tự đăng ký slash commands; `/ask` đã đăng ký thì chỉ cần `make bot-dev`, còn lần đầu thêm lệnh chạy riêng `make bot-deploy` một lần.

Ở **gốc dự án**, terminal chạy API dùng `make api` với môi trường mock của TV1. Terminal bot:

```powershell
make bot-deploy
make bot
```

`make bot-deploy` đăng ký lệnh global (không cần chạy mỗi lần sửa handler). `make bot` giữ terminal mở và không tự bật backend hoặc đổi CHAT_MODE; `Ctrl+C` dừng bot. `make dev` hiện chỉ chạy hạ tầng/API/web như trước, không tự đăng nhập Discord.

Các lệnh dưới đây là **hướng dẫn, chưa được chạy trong tác vụ này**. Cần backend mock sẵn sàng và thông tin Discord hiện có.

```powershell
cd bot
npm.cmd run deploy-commands
npm.cmd run dev
```

Trong Discord gọi `/ask question:Marika là ai?`; kiểm tra defer, embed và link nguồn. Với backend mock của TV1, thử `/mock-slow`, `/mock-error`, `/mock-429`, `/mock-ungrounded`. Lệnh global có thể cần thời gian cập nhật; bot phải được cài và có quyền tại kênh thử nghiệm.

Chưa làm lưu ngữ cảnh theo channel/user, chia nhiều tin, `/help`/`/about`, nút feedback/hỏi tiếp, cấu hình guild hay mention. Các mục đó thuộc S3–S5, không tự triển khai trong S2.

Bàn giao: [Bot ask và API mock TV4](../docs/handover/2026-10-30_s2-tv4_bot-ask-api-mock.md).

---

# Bot TV4 · Sprint 3

## Hành vi

- `/ping`: kiểm tra bot online.
- `/ask question:<câu hỏi>`: deferReply trước I/O, gọi `/api/v1/chat` với service token và X-Request-ID.
  Backend giữ ngữ cảnh bằng external_ref theo kênh/người dùng hoặc thread. Đây là luồng thật; dùng mock hay RAG do cấu hình backend quyết định.
- Câu trả lời dài được chia đủ thành các embed riêng, mỗi mô tả tối đa 3.600 UTF-16 code units, không tách đôi emoji.
  Phần đầu dùng editReply và có nguồn; các phần sau dùng followUp, đánh số phần. Không bật mentions.
- `/help`, `/about`: hướng dẫn/nguồn và CC BY-SA, trả riêng cho người gọi, không gọi backend/LLM.
- Script deploy đăng ký toàn cục toàn bộ bốn lệnh trong registry. Đã chạy ngày 08/11/2026 và đọc lại từ Discord xác nhận đủ bốn lệnh.
  Gateway chẩn đoán và hai lượt handler → backend thật đạt. Sau phản ánh và ảnh mới ngày 08/11/2026,
  `/help` và `/about` ban đầu chưa được xác nhận hiển thị/chạy ở client dù REST có đủ bốn lệnh;
  sau đó người dùng đã gửi ảnh hai lệnh trả lời thành công trên Discord.
  Chưa kiểm tra trực tiếp câu trả lời dài trên Discord.

## Chạy và kiểm tra thủ công

Từ thư mục gốc, mở Docker Desktop rồi chạy `make up` và `make api` ở terminal thứ nhất;
terminal thứ hai chạy `make bot`. Chọn CHAT_MODE của backend theo nhu cầu; không dùng `make bot-dev` để đánh giá RAG thật vì lệnh đó ép mock.

Khi muốn xuất bản định nghĩa lệnh mới lên Discord, tự chạy:

```powershell
make bot-deploy
```

Lệnh này cập nhật global commands, cần Discord token hợp lệ trong `.env`. Không đưa token vào Git.
Sau khi lệnh xuất hiện, thử `/help`, `/about`, `/ask` ngắn, hỏi tiếp cùng kênh/người dùng và câu trả lời dài.
Kiểm tra cả nguồn và thứ tự các phần. Cần dùng server test để xác nhận end-to-end thật.

## Kiểm tra local và giới hạn

Trong `bot/`: `npm.cmd run typecheck`, `npm.cmd test`, `npm.cmd run format:check`.
Các test giả lập interaction/fetch; không cần Discord/backend hoặc gọi model.

Ngày 08/11 người dùng cho phép bổ sung API chia sẻ giới hạn vào backend: bot tạo bản chụp một câu trả lời qua
POST `/api/v1/answer-shares` có service auth, nhận mã ngẫu nhiên 24 giờ và gắn nút “Xem đầy đủ trên web”.
Người có link chỉ đọc bản chụp đó; không được quyền đọc cả hội thoại. Không đưa API_SERVICE_TOKEN vào URL hoặc frontend.
Bot vẫn trả đủ văn bản qua các phần; nếu tạo link lỗi, chỉ ghi loại lỗi và giữ câu trả lời, không tự retry LLM.
Nguồn dài vẫn bị giới hạn theo dung lượng field Discord; bản chia sẻ lấy toàn bộ danh sách nguồn trong câu trả lời lưu ở backend.

Đặt `WEB_URL` thành URL gốc của web mà người nhận truy cập được, không kèm path/query/fragment hoặc thông tin đăng nhập.
URL local hiện dùng Radmin VPN; người nhận cần truy cập được mạng đó. Production dùng URL HTTPS của dự án.
Sau đổi `.env`, dừng rồi chạy lại `make bot` để nhận cấu hình mới. Không cần deploy slash command lại vì không đổi định nghĩa lệnh.
Link chỉ có trong câu trả lời mới sau cập nhật, không tự sửa các tin Discord cũ. Xem `docs/api/answer-shares-tv4.md`.

Ghi nguồn CC BY-SA dựa theo khảo sát `docs/data-sources.md`; không áp giấy phép văn bản cho toàn bộ ảnh/font hoặc nội dung bên ngoài.
