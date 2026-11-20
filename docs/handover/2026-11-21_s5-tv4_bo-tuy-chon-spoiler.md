# TV4 · Bỏ tùy chọn `spoilers` khỏi web, bot và API (TV3 làm thay)

Ngày 21/11/2026 · Nhánh `fix/s4-tv3-tach-han-thoi-gian`, chưa commit. Agent của TV3 (MinhMuc) làm thay phần web/bot của TV4 theo quyết định của TV3: IndexBeast trả lời như một wiki, không cần tính năng tránh spoiler.

## Bối cảnh

Từ trước, backend đã ép `options.spoilers` luôn bằng `true` (validator `allow_spoilers` trong `backend/app/api/schemas/chat.py`). Web và bot không có nút bật/tắt, chỉ luôn gửi `spoilers: true`. Phần còn lại là tham số truyền qua nhiều tầng (corpus policy, vector store, retriever, pipeline, Tool Agent, ảnh) nhưng không còn tác dụng thực.

## Thay đổi

| Phần | File | Thay đổi |
|---|---|---|
| API (TV1) | `backend/app/api/schemas/chat.py` | Xóa trường `ChatOptions.spoilers` và validator. Trường lạ bị Pydantic bỏ qua, nên client cũ gửi kèm `spoilers` **vẫn được chấp nhận** (không 422). |
| Backend | `core/corpus.py`, `core/vector/store.py`, `core/types.py`, `app/rag/{retriever,pipeline,tool_agent,task_plan}.py`, `app/services/{images,answer_media}.py`, `app/rag/prompts/__init__.py` | Bỏ tham số `spoilers` và mọi phép lọc theo `spoiler_level`; bỏ dòng "Spoilers allowed" trong system prompt. |
| Web | `web/src/api/types.ts`, `web/src/hooks/useChatStream.ts`, 3 file test | Bỏ `spoilers` khỏi type `ChatRequest.options` và khỏi request gửi đi. |
| Bot | `bot/src/api/types.ts`, `bot/src/commands/ask.ts`, `bot/src/handlers/message.ts` | Như web. |
| Script/eval | `backend/scripts/{check_retrieval,benchmark_retrieval,audit_images,run_live_acceptance,diagnose_*}.py`, `backend/eval/*` | Bỏ tham số và cờ `--no-spoilers`. |
| Dữ liệu | (không đổi) | `spoiler_level` vẫn là metadata của chunk (ingest, PostgreSQL, payload index Qdrant). `ingest/debug/s4_wiki_eval.py` tự lọc `spoiler_level == 0` để tiếp tục đánh giá nhãn. |

## Kiểm tra đã chạy

- Backend unit: **1.149 passed, 20 skipped**; Ruff check/format đạt.
- Web: `npm run typecheck` đạt; `npm test` **71/71**.
- Bot: `npm run typecheck` đạt; `npm test` **75/75**.
- `pre-commit run --files` trên các file thay đổi: đạt (gồm prettier web và bot).
- Chưa chạy `test:integration` của web, chưa thử trên Discord thật.

## Lưu ý hợp đồng API

Docstring của `schemas/chat.py` ghi xóa trường là thay đổi phá vỡ, cần CHANGE-REQ. Ở đây trường bị bỏ qua chứ không bị từ chối, nên client cũ không hỏng. OpenAPI (`/api/openapi.json`) không còn trường này: nếu TV4 sinh type từ OpenAPI thì sinh lại. Đề nghị TV1 ghi nhận như một CHANGE-REQ.

## Việc còn lại

- TV4: xác nhận không còn chỗ nào trên web/bot hiển thị hoặc nhắc tới spoiler (đã grep `web/src`, `bot/src`: không còn).
- Tài liệu cũ (`web/README-TV2-TV4.md`, handover các sprint trước) còn nhắc nhãn spoiler như lịch sử; không sửa.
