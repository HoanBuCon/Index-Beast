# TV4 · Bot Sprint 2: API client và `/ask`

Mã phía bot đã có kiểm thử độc lập bằng dữ liệu giả. **Chưa nghiệm thu tích hợp Discord → backend thật**, không đồng nghĩa đã đăng ký `/ask` trên Discord.

## Phạm vi

- Types viết tay theo `docs/api/openapi.json`, thích nghi phần hợp đồng công khai đã có trong web; không import mã UI hay sinh lại OpenAPI.
- Client `createApiClient()` có `chat`, `chatStream`, `sendFeedback`, `getConversation`; timeout mặc định 30 giây, `X-Request-ID`, service token tùy chọn, kiểm tra dữ liệu trả về, lỗi thân thiện và giữ `Retry-After` khi 429.
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

- `DISCORD_TOKEN`, `DISCORD_CLIENT_ID`: thông tin Discord hiện có, không ghi vào tài liệu/log.
- `BOT_API_URL`: để trống khi chạy bot trên máy → `http://127.0.0.1:<API_PORT>`; `API_PORT` mặc định 18000. Chấp nhận URL gốc hoặc kết thúc `/api/v1`, không ghép tiền tố hai lần.
- Trong container, Compose hiện đặt `BOT_API_URL=http://api:18000`; `api` là tên service, không phải localhost của máy.
- `API_SERVICE_TOKEN`: gửi `X-Service-Token` nếu được cấu hình khác `change-me`. Theo bàn giao TV1, xác thực service token thuộc S4; client không tự thêm yêu cầu bảo mật vào backend.
- API timeout 30 giây; không tự retry POST để tránh gửi câu hỏi hai lần.

Client không ép backend sang mock. Backend có thể đang ở mode `rag`/`llm_only`; chỉ dùng môi trường mock của TV1 khi nghiệm thu Sprint 2, tránh vô tình gọi LLM trả phí. Không tự sửa mode hoặc `.env` của thành viên khác.

## Khi sẵn sàng kiểm thử tích hợp

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
