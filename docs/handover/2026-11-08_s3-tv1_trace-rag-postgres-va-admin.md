# Lưu trace và số đo từng câu trả lời vào PostgreSQL, endpoint xem trace

| | |
|---|---|
| Ngày | 08/11/2026 |
| Người thực hiện | TV1 (Hoanbucon); pipeline và `chat.py` thuộc TV3 |
| Nhánh | `feature/s3-tv1-trace-rag` (từ `develop` tại `cb2a358`) |
| Thẻ Trello | 3.1 Endpoint /chat & /chat/stream thật (phần lưu số đo), 3.2 Trace từng bước RAG |

## Vấn đề

- Trace chỉ nằm trong RAM (`LiveChatService.traces`, tối đa 1.000 bản): khởi động lại API là mất, nên không thể điều tra vì sao một câu trả lời sai sau đó.
- Bảng `messages` đã có các cột `rewritten_query`, `latency_ms`, `tokens_in`, `tokens_out`, `trace` từ migration `0001` nhưng không được ghi.
- Trang Admin trên web đã gọi `/admin/trace/{id}`, API chưa có route này.

## Đã làm

- **Lưu vào PostgreSQL** (`MemoryRepository.save`, tham số mới `record`): với tin nhắn assistant, ghi `rewritten_query`, `latency_ms`, `tokens_in`, `tokens_out` và `trace.rag`. Hai khóa cũ `images`, `clarification` trong `messages.trace` giữ nguyên. **Không có migration mới.**
- **`app/rag/trace.py`: `public_trace()`** là cửa duy nhất đi vào DB và API:
  - bỏ `result` (nội dung câu trả lời, đã có ở bảng `messages`) và mọi khóa bắt đầu bằng `_`;
  - che giá trị của khóa kiểu `api_key`, `secret`, `password`, `authorization`, `cookie`, `token`, `*_token`, và chuỗi dạng `sk-…`, `Bearer …`, `tvly-…` (các khóa `prompt_tokens`, `completion_tokens` không bị che);
  - cắt chuỗi 1.000 ký tự, danh sách 50 phần tử, độ sâu 8;
  - quá 64 KB thì chỉ giữ `latency_ms`, `usage`, `rewrite`, `rewritten_query` kèm `truncated`, `bytes`, `keys`.
- **`token_usage()`**: `tokens_in/out` là tổng token của lượt sinh câu trả lời và lượt viết lại truy vấn. Các lượt gọi LLM khác (agent, đánh giá bằng chứng, tool) chưa được cộng, nên con số là cận dưới.
- **`pipeline.py`**: thêm `trace["rewritten_query"]` (một dòng, trước khi truy xuất).
- **`GET /api/v1/admin/trace/{message_id}`** (`app/api/routes/admin.py`), cần header `X-Admin-Token`:
  - chưa cấu hình `ADMIN_TOKEN` (bỏ trống hoặc `change-me`) → **404**, coi như route không tồn tại;
  - sai token → 401; so sánh bằng `hmac.compare_digest`;
  - đọc PostgreSQL trước, không có thì lấy bản trong RAM (`source: "memory"`, mất khi khởi động lại); không thấy → 404.
- **CLI**: `make trace ID=<message_id>` hoặc `python -m scripts.trace <message_id>`; chỉ đọc PostgreSQL, không cần chạy API.
- Cấu hình: `ADMIN_TOKEN` trong `core/config.py`, `.env.example`, `docker-compose.yml` (mặc định rỗng để production không báo "còn giá trị mẫu"). `docs/api/openapi.json` xuất lại (chỉ thêm route mới).

## Kiểm tra trên máy TV1

| Kiểm tra | Kết quả |
|---|---|
| Backend unit test | 829 passed |
| Test tích hợp PostgreSQL thật (DB tạm): `test_trace_store`, `test_db_schema` | 11 passed |
| ruff check, ruff format | đạt |

Test mới: che secret và giới hạn cỡ, tổng token, quyền truy cập endpoint (không cấu hình, sai token, token đúng, không có message, id sai), lưu và đọc lại qua SQLite giả lập, lưu qua service rồi dựng service mới (trace còn sau khi khởi động lại), lưu trên PostgreSQL thật.

## Chưa làm hoặc chưa kiểm tra

- **Chưa gọi DeepSeek thật** để xem trace của một câu hỏi thật; chỉ chạy bằng LLM giả (theo `docs/AGENTS.md`). Cần chạy thử một câu hỏi rồi `make trace ID=…` để xem trace thực tế.
- **Kích thước trace thật chưa đo.** Nếu thường vượt 64 KB (nhiều nguồn web), cần tách trace sang bảng riêng.
- `memory_sync` (đồng bộ bộ nhớ ngữ nghĩa, chạy sau khi lưu) chỉ có trong bản trace trong RAM, không có trong bản ở PostgreSQL.
- `/admin/stats` (thẻ S5) vẫn chưa có; trang Admin web chỉ xem được trace.
- Không có cơ chế tự xóa trace cũ.

## Cần TV3 xem lại

`chat.py` (`_save`, `LiveChatService.trace`), `memory_repository.py` (`save`, `trace`) và một dòng trong `pipeline.py` thuộc phần TV3 đang phát triển. Thay đổi chỉ thêm tham số tùy chọn và dữ liệu ghi thêm, không đổi luồng xử lý.
