# Kiểm thử model decisions và semantic memory — offline

06/11/2026 · TV3 — MinhMuc · IndexBeast / 4 Hollows.

## Baseline và phạm vi

Tác vụ tiếp nối bản LangGraph/lexical trước, giữ toàn bộ modified/untracked của người dùng.
Nhánh mới `feature/s3-tv3-agent-semantic-memory` từ HEAD local `eeccb93`; không reset/stash/rebase.
Baseline chạy lại, không lấy số trong handover làm kết quả: **740 passed, 1 warning, 24,06 giây**.

Đã triển khai quyết định bằng mô hình, semantic retrieval với PG canonical check, persistence/restart,
capability transport và runner live riêng. Bảng trách nhiệm/graph/setup nằm trong
[tài liệu agent](../api/agent-semantic-memory.md).

## Kiểm thử

31 case mới trong `backend/tests/unit/test_agent_durable.py` gồm:

- Default agent và thực thể ngoài danh sách weapon cũ; không gọi legacy `advance` trên đường agent.
- Structured action, memory IDs, source provenance, số/goal/phủ định, schema lỗi và provider lỗi.
- General build không bị ép hỏi profile, smalltalk không phải tạo query giả, reply language khóa theo request.
- Dual giữ English + original VI cho câu độc lập, context generator không lấy history làm evidence.
- Off/auto/always và logical-call budget trước generation.
- Lưu/restore conversation và pending, capability hash, scope khác conversation và owner khác cùng conversation.
- Retry cùng turn_id không gọi model/lưu lại, nội dung khác cùng key bị từ chối.
- Revision CAS/rollback, fact supersession, vector stale, rebuild/upsert idempotent và pending khi vector lỗi.
- SSE abandon không commit; SSE replay không gọi model; GET history/feedback khôi phục với capability.
- Dense-only encoder dùng một prefix, không BM25, không truncate input dài.
- CLI plan-only không client; manifest 20 lượt; migration 0001→0002 chỉ thêm bảng, sinh SQL offline.

Fake provider dùng decision JSON có cấu trúc, không giả rằng model thật nhận intent đúng.
Repository chạy SQL thật qua facade trên SQLite tạm, compiler JSONB dành riêng cho test;
**không phải asyncpg/PostgreSQL integration**. Qdrant memory chạy Query API với vector 384 tổng hợp;
không dùng nó để báo recall E5 hoặc xác nhận payload index/HNSW server.

Suite provider cũ chủ động đặt `CHAT_AGENT_ENABLED=false` trong fixture để tiếp tục kiểm đường tương thích,
vì fake cũ không có decision output. Test agent mới luôn bật flag rõ ràng, có test kiểm default flag thật.
Không mô tả 740 legacy regression là 740 phép đo chất lượng agent. Giữ assertion citation, JSON, quote,
build feasibility, failure, cancellation và contract cũ, không xóa để làm test xanh.

Web thêm 3 test `memoryTransport.test.ts`: JSON/SSE token propagation, header history/feedback,
localStorage capability và đọc conversation legacy. Không đổi giao diện TV4 hoặc code bot.

Các lệnh kiểm đã chạy từ backend:

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest -c pyproject.toml tests/unit -q
.venv/Scripts/python.exe -m ruff check app core scripts tests/unit/test_agent_durable.py tests/unit/test_memory_graph.py tests/conftest.py
.venv/Scripts/python.exe -m scripts.export_openapi
.venv/Scripts/python.exe -m scripts.export_openapi --check
.venv/Scripts/python.exe -m pip check
```

Từ web:

```powershell
node --test --test-concurrency=1 --test-timeout=30000 tests/*.test.ts
npm run build
npx prettier --check src/api/types.ts src/api/client.ts src/api/chat.ts src/hooks/useChatStream.ts src/lib/storage.ts tests/memoryTransport.test.ts
```

Lượt toàn suite cuối: **771 passed, 2 warnings, 22,45 giây**, gồm kiểm owner ở cả SQL recent recall
và vector revalidation. Nhóm agent/durable có 31 case; baseline 740 case vẫn được giữ.
Web **40/40**, build/typecheck, Ruff/format (111 file) và pip check đạt.
Đã kiểm UTF-8, 121 liên kết local trong 8 tài liệu và `git diff --check`; report/manifest hash khớp. OpenAPI có field token/turn_id và lỗi auth/storage mới.

Hai warning: Qdrant memory không thực thi payload index; Alembic `prepend_sys_path` chưa đặt path_separator.
Không phải failure hoặc xác minh server thật. Dependency mới của lượt trước giữ nguyên, task này không cài model/library mới.

## Phát hiện và giới hạn

- Refactor dense-only ban đầu làm embed trước sparse init thành công; test cũ bắt lỗi CPU inference thừa.
  Đã trả về thứ tự khởi tạo an toàn, giữ nguyên assertion số lượt embed cũ.
- Entity/constraint guard đường agent không dùng classifier tên/intent cũ; provenance vẫn kiểm bằng literal.
- Scope được kiểm cả SQL và Qdrant; không dựa riêng vào scope object hoặc payload.
- Planner provider failure trả lỗi thật, không biến thành clarification thành công.
- Không chấm accuracy, recall, faithfulness hoặc độ tự nhiên của model bằng fake fixtures.
- `.env` thật vẫn cho `chat_mode=rag`, `chat_agent_enabled=true`, `chat_persistence=memory` ở lần kiểm cuối.
  PostgreSQL semantic memory **chưa được bật/kiểm chứng trên runtime thật**.
- Live preflight **blocked, 0/20**, không có DeepSeek/Tavily/embedding thật; xem
  [báo cáo preflight](2026-11-06_agent-memory-20/README.md).
- Chưa test migration/asyncpg thật, embedding semantics, ANN server, full process restart hoặc Discord gateway.
- Không sửa corpus/golden/report cũ, `.env` thật, OS virtualization hoặc dữ liệu production; chưa commit/push/merge.

Auth per conversation không phải hệ tài khoản; không có cross-chat profile hay UI quản lý/xóa memory.
Raw history retention còn do operator. Model-call budget là logical, transport retries riêng;
benchmark sẽ tắt SDK retry nếu sau này được chạy. Code sẵn sàng thử không đồng nghĩa chất lượng live đã được chứng minh.
