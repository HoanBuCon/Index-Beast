# Sprint 2 TV1: hợp đồng API v1, mock và lỗi chuẩn

| | |
|---|---|
| Ngày | 28/10/2026 |
| Người thực hiện | TV1 (Hoanbucon) |
| Nhánh | `feature/s2-tv1-api-contract-v1` (từ `origin/develop`; chưa có PR khi viết tài liệu này) |
| Thẻ Trello | *API contract v1 (OpenAPI) + mock* và *Xử lý lỗi & logging chuẩn* |

## Phạm vi

Hai thẻ đầu của TV1 ở S2. Thẻ *Schema PostgreSQL & migrations* làm ở nhánh riêng sau đó, không thuộc handover này. Chưa có pipeline RAG: `/chat` trả dữ liệu giả để web và bot làm song song.

## Đã làm

- **Endpoint mock** dưới `/api/v1`: `POST /chat`, `POST /chat/stream` (SSE), `POST /feedback` (204), `GET /conversations/{id}`. Dịch vụ giả nằm ở `backend/app/services/mock_chat.py`, giữ hội thoại trong RAM (tối đa 500). S3 thay bằng service RAG thật, giữ nguyên route và schema.
- **Schema** (`backend/app/api/schemas/`): `ChatRequest` (`conversation_id`, `message` ≤ 2000 ký tự, `channel` web/discord, `external_ref`, `options`), `ChatResponse`, `Source`, các event SSE (`status`, `token`, `sources`, `done`, `error`), `FeedbackRequest` (`rating` chỉ 1 hoặc -1), `ConversationOut`.
- **Hợp đồng xuất ra file**: [`docs/api/openapi.json`](../api/openapi.json) (không gồm `/dev/*`). `make openapi` ghi lại; CI chạy `python -m scripts.export_openapi --check` và fail nếu file lệch code.
- **Lỗi chuẩn**: mọi lỗi trả `{code, message, request_id}` (`core/errors.py`, `app/api/errors.py`). Có `bad_request`, `unauthorized`, `not_found`, `validation_error`, `rate_limited` (kèm `Retry-After`), `upstream_error`, `unavailable`, `internal_error`. Lỗi 422 chỉ nêu tên trường, không lặp lại dữ liệu người dùng gửi. Lỗi chưa bắt được trả JSON 500 không lộ chi tiết, request id lấy từ middleware.
- **Request id và thời gian xử lý**: `X-Request-ID` hợp lệ từ web/bot được giữ và trả lại; middleware log phương thức, đường dẫn, status và ms (đã có từ S1, nay cả response 500 cũng được log).
- `/dev/llm/test` (TV3) đổi sang `UnavailableError`/`UpstreamError`: trường `detail` thành `message`. Test tương ứng đã sửa.

## Cách dùng cho TV4 và TV3

- Web/bot viết type tay theo `docs/api/openapi.json`. Chỉ thêm trường tùy chọn; đổi hoặc xóa trường cần thẻ CHANGE-REQ.
- Thử trạng thái lỗi bằng cách gửi `message` là `/mock-ungrounded`, `/mock-error`, `/mock-429` hoặc `/mock-slow`.
- Stream: lỗi xảy ra trước khi bắt đầu stream (hội thoại không có, quá tốc độ) trả JSON và mã HTTP đúng; lỗi giữa chừng gửi event `error` rồi đóng.
- **Chưa có xác thực**: `X-Service-Token` mà bot gửi chưa được kiểm tra (thuộc S4).
- Khác biệt với bản nháp SRS §5.1: dùng `external_ref` thay `client_user_ref`; `/admin/*` chưa có (S5).

## Kiểm tra đã chạy

- `pytest` backend: 89 passed, 1 integration deselected (10 test mới trong `tests/unit/test_chat_api.py`).
- `ruff check` và `ruff format` đạt cho `app`, `core`, `scripts`, `tests`.
- `python -m scripts.export_openapi --check` đạt.
- Chưa chạy: integration test với service thật, web và bot với endpoint mới, CI trên GitHub.

## Còn lại

- Review hợp đồng với TV3 và TV4 (mục cuối của thẻ); TV4 đối chiếu type trong `web/src/api/types.ts` và `bot/src/api/types.ts`.
- Cập nhật SRS §5.1 sau khi team chấp nhận hợp đồng.
- Thẻ Schema PostgreSQL: models, migration đầu tiên, repository, test với Postgres thật.
