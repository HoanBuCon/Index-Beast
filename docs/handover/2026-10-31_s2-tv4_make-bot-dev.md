# TV4 · Một lệnh chạy bot với API mock

Ngày: 31/10/2026 (Asia/Saigon). Nhánh `feature/s2-tv4-bot-ask-api-mock`. Chưa commit/push trong tác vụ này.

## Phạm vi

Theo yêu cầu chạy bằng một lệnh, thêm target `bot-dev` vào Makefile gốc. Không sửa mã backend, cấu hình .env, Docker Compose hoặc công việc TV1–TV3. Giữ target và ghi chú cũ; gọi lại `up`, `api`, `bot` hiện có. Cập nhật `bot/IMPLEMENTATION.md` và chỉ mục handover TV4.

## Cách dùng

Mở Docker Desktop và chờ engine sẵn sàng, sau đó ở gốc repo chạy:

```powershell
make bot-dev
```

Lệnh chờ hạ tầng healthy rồi chạy API và bot song song cùng terminal. Target-specific export đặt `CHAT_MODE=mock` và `BOT_API_URL=http://127.0.0.1:<API_PORT>` cho các tiến trình con, không sửa `.env` hay cấu hình backend của TV1. Backend dùng Python venv và bot đọc cấu hình Discord như các target cũ. Chờ API startup complete và bot online trước khi hỏi.

Cần cài sẵn dependency và thông tin Discord hợp lệ. Dừng bản API/bot đang chạy ở terminal khác để tránh trùng cổng/phiên bot. Giữ terminal mở; Ctrl+C để dừng API/bot, Docker không tự down. Đăng ký `/ask` lần đầu vẫn dùng riêng `make bot-deploy`; không tự gọi Discord REST đăng ký lệnh mỗi lần chạy.

## Kiểm tra thực tế

- `make -n bot-dev` đạt: lệnh Docker up/wait, recursive make song song api/bot đúng.
- Kiểm tra thực thi điều phối bằng hai probe Node tạm thay COMPOSE/MAKE, với môi trường ban đầu CHAT_MODE=rag và BOT_API_URL tên service Docker: cả hai probe nhận mock và URL localhost cổng override 19001; xác nhận không lặp prefix hay phụ thuộc việc nhập biến thủ công. Probe không gọi Docker/backend/Discord/LLM, được dọn sau test.
- Prettier cho hướng dẫn và `git diff --check` đạt.
- Chưa thực thi target với dịch vụ thật hoặc nghiệm thu Discord end-to-end; không gọi LLM, không chạy thêm bot và không dừng tiến trình của người dùng trong tác vụ này.

Không thay đổi logic bot nên không chạy lại bộ unit test đã đạt ở handover triển khai. Xem [bàn giao bot Sprint 2](2026-10-30_s2-tv4_bot-ask-api-mock.md) và [hướng dẫn bot](../../bot/IMPLEMENTATION.md).
