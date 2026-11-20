# TV3 · Gỡ chế độ chat `llm_only`

Ngày 20/11/2026 · Nhánh `refactor/s4-tv3-go-llm-only` (tách từ `origin/develop` tại `f930de3`). Chưa push, chưa có PR.

## Phạm vi và quyết định

Người dùng (TV3) xác nhận chế độ `llm_only` (gọi DeepSeek trả lời không truy xuất, không nguồn) không còn dùng. `CHAT_MODE` giờ chỉ nhận `mock` (mặc định) hoặc `rag`. Không còn đường trả lời nào bỏ qua truy xuất và kiểm bằng chứng.

**Thay đổi không tương thích:** `.env` còn `CHAT_MODE=llm_only` làm Settings báo lỗi validate, API không khởi động. Cần đổi sang `mock` hoặc `rag`. Docker compose staging/prod đã dùng `rag`, compose dev mặc định `mock`.

## Thay đổi mã

- `backend/core/config.py`: `chat_mode: Literal["mock", "rag"]`.
- `backend/app/context.py`: luôn tạo Qdrant client. Health probe vẫn tự tạo client khi context không có client (fake trong test).
- `backend/app/services/factory.py`: ngoài `mock` thì luôn dựng `HybridRetriever`; bỏ nhánh `retriever = None`.
- `backend/app/rag/pipeline.py`: bỏ `_rag()`, bỏ nhánh memory riêng của llm_only và prompt `llm_only`; graph đi thẳng `memory → agent_decision`; history cho generation luôn rỗng.
- `backend/app/rag/generator.py`: bỏ các nhánh kiểm `mode`; generation luôn dùng JSON, parser grounded, stream prefix và retry định dạng.
- `backend/app/services/chat.py`: bỏ `notice()` (câu "Chế độ LLM: …" chèn đầu JSON/SSE).
- Xóa `backend/app/rag/prompts/llm_only.md`.
- `backend/scripts/run_live_acceptance.py`: bỏ ca kiểm llm_only và hai import không dùng. Sửa chú thích trong `privacy.py`, `api/routes/chat.py`, `loadtest/locustfile.py`.

## Thay đổi test

- Xóa các test chỉ dành cho llm_only: không retrieval/grounding, không tạo encoder, không tạo Qdrant/reranker, cấm citation/URL, không retry JSON.
- Chuyển sang `rag` với `FakeRetriever` và token JSON grounded (helper `rag_tokens()` trong `test_live_chat.py`): stream tăng dần và đóng provider, hủy stream, đổi mode qua message, JSON API + feedback, lỗi provider trước/giữa stream, thinking, history và cách ly kênh.
- Health probe: test mới kiểm probe dùng lại client Qdrant của context.
- `test_chat_guard.py`: guard chạy ở `rag`; test lịch sử bot theo `external_ref` kiểm số memory candidate thay cho history của generation; test timeout làm chậm `complete_json`.
- `test_discord_guild_api.py`, `test_images.py`, `test_reranker_wiring.py`: bỏ tham số hoặc mode `llm_only`.

## Thay đổi tài liệu

`.env.example`, `README.md`, `docs/01_TECHSTACK.md`, `backend/app/rag/README.md`, `docs/api/{agent-semantic-memory,images-tv4,langgraph-memory,web-search-tv4}.md`, `docs/indexbeast-system-pipeline.md`, `bot/IMPLEMENTATION.md`.

Trong `docs/01_TECHSTACK.md` cũng sửa các dòng còn nhắc cờ đã gỡ trước đó (`CHAT_AGENT_ENABLED`, `CHAT_TOOL_AGENT_ENABLED`, `RAG_REWRITE_*`, `RAG_QUERY_MODE`, `rewrite.py`, `query_plan.py`). Danh sách prompt trong `backend/app/rag/README.md` cập nhật theo file thật. Handover và báo cáo test cũ giữ nguyên vì là lịch sử.

## Kiểm tra đã chạy (offline, không gọi dịch vụ trả phí)

- `backend\.venv\Scripts\python.exe -m pytest -q`: **1.153 passed, 20 skipped**.
- `ruff check .` và `ruff format --check .` trong `backend/`: đạt.
- `pre-commit run --files` cho các file thay đổi: đạt.
- `git grep llm_only` (trừ `docs/handover`, `docs/testing`): chỉ còn ba câu ghi chú rằng mode đã bị gỡ. Web và bot không có mã nào dùng `llm_only`.
- Chưa chạy API thật, Docker hay DeepSeek/Jina/Tavily cho thay đổi này.

## Còn lại

- `docs/api/langgraph-memory.md` (sơ đồ còn node `rewrite`) và vài câu trong `backend/app/rag/README.md` vẫn mô tả nhánh rewrite legacy. `docs/production.md` theo ghi chép trước đó còn nhắc `CHAT_AGENT_ENABLED`, chưa kiểm lại.
- `Prepared.mode` vẫn giữ (luôn là `rag` trong pipeline), dùng cho trace và kiểm ảnh trong `chat.py`.
- Các việc rà soát tiếp theo của TV3: bỏ rule con số viết cứng trong `agent.py`, tách hạn chuẩn bị và stream, giới hạn bước khi web `auto`, chuyển việc sửa chính tả tên cho Agent, dọn fallback do server tự chọn.
