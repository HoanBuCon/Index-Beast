# Sprint 2 TV1: rate-limit, hội thoại bot theo external_ref, hạn thời gian

| | |
|---|---|
| Ngày | 31/10/2026 |
| Người thực hiện | TV1 (Hoanbucon) |
| Nhánh | `fix/s2-tv1-rate-limit-hoi-thoai-timeout` (từ `origin/develop` tại `35cce86`, sau PR #47; chưa có PR khi viết) |
| Căn cứ | Phát hiện #1–#3 trong [báo cáo bàn giao Sprint 2](2026-10-31_s2-tv1_bao-cao-ban-giao-sprint-2.md) |

## Đã sửa

### #1 API gọi LLM thật không có xác thực và rate-limit

- `backend/app/api/guard.py`: `enforce_chat_limits` chạy đầu `/chat` và `/chat/stream`, **chỉ khi `CHAT_MODE` là `llm_only` hoặc `rag`** (mock không tốn tiền nên bỏ qua).
- Request `channel=discord` phải có `X-Service-Token` khớp `API_SERVICE_TOKEN`, nếu không trả 401. Mục đích: không ai giả làm bot để né giới hạn theo IP.
- Giới hạn `RATE_LIMIT_PER_MINUTE` (mặc định 10) theo cửa sổ 1 phút trong Redis. Bot đã xác thực được tính theo `external_ref` (mọi request của bot cùng một IP); web tính theo IP. Vượt giới hạn trả 429 kèm `Retry-After`.
- Redis lỗi thì trả 503, **không** mở cửa cho request không giới hạn.
- Compose truyền `API_SERVICE_TOKEN`, `RATE_LIMIT_PER_MINUTE`, `CHAT_TIMEOUT_SECONDS` vào service `api`. Trước đây chỉ bot nhận token.

### #2 Bot mất ngữ cảnh và đẩy hội thoại web ra khỏi bộ nhớ

- `LiveChatService` và `MockChatService`: khi không có `conversation_id` mà có `external_ref`, dùng lại hội thoại cũ của cặp `(channel, external_ref)`. Mỗi thread Discord, hoặc mỗi user trong một channel, giữ một hội thoại, nên câu hỏi tiếp theo có lịch sử.
- Kho RAM đổi sang thải hội thoại ít dùng gần đây nhất (trước đây thải theo thứ tự tạo). Khi thải thì xóa luôn ánh xạ `external_ref`.
- Bot không cần sửa: bot đã gửi `external_ref` từ S2.

### #3 Bot bỏ cuộc trước backend

- `CHAT_TIMEOUT_SECONDS` (mặc định 45) là hạn tổng cho một câu hỏi ở `/chat`: gồm chờ khóa hội thoại, LLM kể cả retry, và ảnh. Hết hạn thì hủy lời gọi LLM và trả **504** `timeout`. Với `/chat/stream`, hạn chỉ tính tới token đầu tiên.
- Timeout mặc định của bot tăng từ 30 lên **60 giây**, lớn hơn hạn của backend, để bot luôn nhận được 504 thay vì tự bỏ cuộc trong khi backend vẫn chạy và tính tiền token.

## Lưu ý vận hành

- **Đặt `API_SERVICE_TOKEN` thật** (cùng giá trị cho bot và api) trước khi chạy bot với `CHAT_MODE` khác mock. Nếu để `change-me`, mọi `/ask` sẽ bị 401.
- Ở dev, web đi qua proxy Vite nên mọi người dùng LAN/VPN có cùng IP `127.0.0.1`, tức dùng chung một hạn mức 10 câu/phút. Production qua Caddy thì `--proxy-headers` cho IP thật.
- Compose chạy `API_WORKERS=2`. Kho hội thoại trong RAM không chia sẻ giữa các worker, nên câu hỏi tiếp theo có thể vào worker khác và mất ngữ cảnh. Cần chuyển sang PostgreSQL ở S3; trước đó demo chế độ live với 1 worker.
- `docs/api/openapi.json` đã sinh lại: thêm mã lỗi 401 và 504 cho `/chat`, `/chat/stream`. Không đổi schema request hay response.

## Kiểm tra đã chạy

- `pytest` backend: **365 passed**, 20 skipped (mẫu raw không có trong Git); 8 test mới trong `tests/unit/test_chat_guard.py` cho: giới hạn theo IP, 401 thiếu token, giới hạn riêng từng thread bot, Redis lỗi → 503, mock bỏ qua guard, dùng lại hội thoại (live và mock), hết hạn → 504 và nhả khóa.
- `FakeRedis` dùng chung trong `tests/conftest.py` có thêm `pipeline` để các test chế độ live cũ chạy qua guard.
- `pytest -m integration`: 15 passed. `ruff check`, `ruff format --check`, `export_openapi --check` đạt.
- Bot: 21/21 test, typecheck và Prettier đạt. Web: 24/24 test, typecheck đạt.
- Chưa chạy: với DeepSeek thật, Redis thật trong luồng chat, Discord thật.
