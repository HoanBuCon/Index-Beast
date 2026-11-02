# TV4 · Sprint 2: Bot `/ask` và API client

Ngày: 30/10/2026 (Asia/Saigon). Chủ sở hữu: TV4 — QuyVuiVe.
Nhánh: `feature/s2-tv4-bot-ask-api-mock`. Chưa commit/push, chưa mở PR hoặc merge trong tác vụ này.

## Phạm vi và quy ước

Triển khai phần độc lập của hai thẻ TV4 trong [kế hoạch Sprint 2](../../planning/sprint_plan.json): **File api.ts viết tay cho web & bot**, **Bot /ask gọi API mock**. Đã đọc README planning/docs, SRS, techstack, kiến trúc, quy ước Git và bàn giao API TV1; hợp đồng thực thi dựa trên [OpenAPI v1](../api/openapi.json), không dựa trường `client_user_ref` của bản nháp SRS.

Chỉ sửa `bot/` và thêm bàn giao TV4/liên kết chỉ mục. Không sửa web, backend, RAG, ingestion, dữ liệu, OpenAPI, planning, Docker Compose, `.env`, root README hoặc phần việc TV1–TV3. Giữ chú thích cũ, không tự đồng bộ những khác biệt scope trong tài liệu cũ và bàn giao mới của TV3. Bot chuyển câu hỏi tới API, không tự triển khai bộ lọc nội dung.

## Thay đổi

| File | Nội dung |
|---|---|
| `bot/src/api/types.ts` | Sao chép/thích nghi types công khai từ web theo OpenAPI, giới hạn 2.000/500 ký tự, nullable source, UUID, event SSE |
| `bot/src/api/client.ts` | Factory tiêm fetch cho test; JSON chat, SSE, feedback, hội thoại; timeout 30 giây, kiểm tra response, request ID, service token tùy chọn, không retry ngầm |
| `bot/src/config.ts` | Thêm `loadApiConfig` riêng để test API không cần Discord token; URL localhost/container, tránh lặp `/api/v1`, kiểm tra URL/cổng |
| `bot/src/commands/ask.ts` | Defer ngay, lấy question, gửi channel discord/external_ref, trả embed, xử lý lỗi thân thiện; cùng UUID trong X-Request-ID và log lỗi |
| `bot/src/commands/index.ts` | Giữ `/ping`, thêm `/ask`; kiểu data chỉ yêu cầu name/toJSON để nhận command có options |
| `bot/src/utils/format.ts` | Embed tối đa title 200, description 3.600, nguồn 1.000 ký tự; chỉ link HTTP(S), tổng dưới 6.000, cảnh báo rút gọn/thiếu bằng chứng |
| `bot/tests/api.test.ts`, `bot/tests/ask.test.ts` | Kiểm thử giả lập API và Discord interaction, không đọc .env hoặc mở mạng |
| `bot/IMPLEMENTATION.md` | Cách test độc lập, cấu hình, hướng dẫn kiểm thử tích hợp để thực hiện sau |

`external_ref` theo thread hoặc channel + SHA-256 user ID, tối đa 128 ký tự; không gửi raw Discord user ID trong request/log. Không lưu hội thoại bền vững hoặc tự nhận đã hoàn thành ngữ cảnh S3. Nguồn thiếu/URL không an toàn không tạo liên kết giả. Nội dung dài có thể bị rút gọn, link xem đầy đủ và chia nhiều tin còn ở S3.

S2 dùng `/chat` JSON. `chatStream`/feedback/conversation có sẵn phía client theo thẻ types/client, chưa gắn thành nút Discord của S4. Giữ đăng ký lệnh global theo yêu cầu trước; không đổi về guild-scoped hoặc tự chạy deploy.

## Kiểm tra thực tế

Từ `bot/` đã chạy:

```powershell
npm.cmd run typecheck
npm.cmd test
npm.cmd run format:check
```

TypeScript đạt; **21/21 test đạt** (2 cũ S1, 19 mới); Prettier đạt. Các ca gồm request/response theo OpenAPI, nullable nguồn, request ID, service token, timeout cả đọc body, hủy, HTTP 401/403/404/422/429/500, không lộ provider body, SSE UTF-8/CRLF và cleanup/thiếu done, feedback, hội thoại, defer trước API, user hash, embed dài và URL không an toàn. Lỗi giả lập có log error là hành vi dự kiến, không phải test thất bại.

Trong lúc triển khai phát hiện nội dung tiếng Việt mới bị mất dấu khi đưa qua Python/stdin PowerShell; đã sửa bằng patch UTF-8 và kiểm tra lại. Một assertion hủy stream ban đầu không đúng khi stream đã đóng; thay bằng ca early-stop riêng xác nhận cancel callback, giữ test Unicode và done/error. Không sửa mã TV1 để làm test qua.

Không cài thêm dependency. Không gọi backend thật, Discord Gateway/REST, LLM, model hoặc Docker. Không chạy `deploy-commands` và không thay đổi cấu hình server Discord.

## Trạng thái checklist và bước phối hợp để sau

- Types/client, mã `/ask`, registry, xử lý timeout/lỗi, X-Request-ID và test độc lập: đã triển khai.
- **Chưa nghiệm thu toàn luồng Discord → backend mock của TV1.** Không tự đánh dấu thẻ tích hợp Done hoặc review nhóm đã xong.
- Cần đăng ký command và thử trên server test khi người dùng sẵn sàng; đảm bảo API đang ở mock vì client không tự đổi backend mode (backend hiện có thể hỗ trợ rag/llm_only và gọi trả phí).
- S3–S5: conversation_id theo channel/user, chia nhiều tin/link thật, help/about, feedback/thread/config/mention vẫn là phần sau.

Hướng dẫn chi tiết: [bot/IMPLEMENTATION.md](../../bot/IMPLEMENTATION.md). Không ghi token hoặc giá trị .env thật vào tài liệu.

## Bổ sung theo yêu cầu: lệnh Makefile cho bot

Người dùng cho phép thêm lệnh chạy bot vào Makefile gốc. Bổ sung ba target TV4: `make bot` chạy dev, `make bot-deploy` đăng ký slash commands global, `make bot-check` chạy typecheck/test/Prettier độc lập. `BOT_NPM` chọn npm.cmd trên Windows, npm trên Linux/macOS và cho phép ghi đè. Bổ sung `.PHONY`; mở rộng regex `make help` để hiển thị target có dấu gạch nối. Giữ recipe và ghi chú api/web/dev cùng các target khác.

Đã thực thi **`make bot-check`: TypeScript đạt, 21/21 test đạt, Prettier đạt**. Đã dry-run `make -n bot`, `make -n bot-deploy`, kiểm tra ghi đè `BOT_NPM=npm` và dry-run api/web; lệnh đúng. Chưa thực thi `make bot` hoặc `make bot-deploy`, chưa kết nối Discord, bật backend/Docker hoặc gọi LLM. Chỉ cập nhật Makefile trong phần lệnh bot được yêu cầu và hướng dẫn TV4; chưa commit/push.

Chạy ở gốc repo: khi backend mock đã sẵn sàng trong terminal riêng, chạy `make bot-deploy` một lần để đăng ký `/ask`, sau đó `make bot` và giữ terminal mở. Ctrl+C dừng bot. `make dev` vẫn chỉ khởi chạy hạ tầng/API/web, không tự chạy bot và không đổi CHAT_MODE.
