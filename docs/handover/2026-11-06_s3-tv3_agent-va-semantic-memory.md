# TV3 — Model decisions và semantic memory lưu bền

06/11/2026 · MinhMuc · IndexBeast / 4 Hollows.

## Phạm vi/Git

Theo yêu cầu người dùng: chuyển quyết định intent/rewrite/gameplay/clarification sang mô hình,
semantic recall và persistence trong cùng conversation, thử thật đúng 20 user turn.
Nhánh `feature/s3-tv3-agent-semantic-memory`, tách từ HEAD local `eeccb93` và giữ toàn bộ thay đổi
chưa commit của bản LangGraph/lexical trước. Không fetch/rebase/stash/reset, commit/push/merge hoặc Trello Done.

**Phần live chưa hoàn thành**: preflight dừng, 0/20 lượt và 0 call trả phí.
Docker báo `WslVirtualMachinePlatformNotEnabled`; PostgreSQL/Qdrant không kết nối được.
Không tự sửa optional feature Windows/reboot hoặc dùng production thay test resource.

## Thay đổi chính

| File/nhóm | Vai trò |
|---|---|
| `backend/app/rag/agent.py`, `prompts/agent.md` | Structured decision: intent, turn type, rewrite/query, memory selection, constraints, clarify/respond/retrieve |
| `backend/app/rag/pipeline.py`, `generator.py` | Conditional LangGraph agent path, evidence separation, logical budget, generation/repair cũ |
| `backend/app/rag/semantic_memory.py` | E5 dense recall ở collection riêng, scope/model/revision filter, đối chiếu PG, bounded sync |
| `backend/app/services/memory_repository.py`, `chat.py`, `factory.py` | Source of truth PG, restore, CAS, capability, replay turn_id, commit trước cache/success |
| `backend/core/db/models.py`, `migrations/versions/0002_agent_memory.py` | Hai bảng cộng thêm: working runtime và memory; giữ conversation/message cũ |
| `backend/core/encoders/onnx.py` | Dense-only chung model/lock, đúng prefix/token limit/worker lifecycle |
| Schemas/routes/middleware/OpenAPI | Token/turn_id tùy chọn, history/feedback auth và CORS header |
| `web/src/api/*`, hook/storage | Transport capability tối thiểu; không thiết kế lại UI/bot |
| `backend/core/config.py`, `.env.example`, compose | Flags/defaults/budget; `.env` thật không sửa |
| `scripts/memory_admin.py`, `scripts/diagnose_agent_memory.py`, `eval/agent_memory_20.json` | Plan-only/operator setup, fixed 20-turn runner, resource test riêng |
| `tests/unit/test_agent_durable.py`, `tests/conftest.py`, `web/tests/memoryTransport.test.ts` | Agent/persistence/scope/replay/semantic mechanics và transport regression |

Default RAG agent không dùng lexical history hoặc regex gameplay để quyết định intent/slot.
Legacy path vẫn có khi chủ động tắt agent; không tự fallback sang nó lúc model lỗi.
Server giữ auth, schema/provenance, số/goal/phủ định, tool policy, deadline, citation và calculator.
Mô hình được chọn có cần hỏi không và hỏi gì; weapon/class không còn là allowlist đóng trên đường agent.

## Memory và contract

PG lưu raw conversation và working/pending state. Memory topic/fact có user-message provenance,
active/superseded và revision; Qdrant chỉ là index dẫn xuất, không có plaintext chat trong payload.
Điểm memory UUID5 theo conversation/message/kind/key, point ID bằng memory UUID; corpus ID giữ nguyên.
Dense 384 cosine, E5 dùng chung encoder, không BM25 cho memory; không truncate hay load model khi import.
Recall tối đa 6 vector + 2 recent user topics trong budget, model chọn ID liên quan.
Assessor/generator không lấy memory làm evidence, không dùng assistant answer cũ làm factual authority.

Web nhận capability token riêng conversation, DB chỉ lưu hash; UUID không đủ quyền.
Client giữ token qua JSON/SSE/storage; history/feedback dùng header. Retry cùng turn_id/nội dung replay từ PG.
Không có cross-chat identity, account recovery, guarantee exactly-once khi mất response tạo conversation đầu tiên,
distributed queue hoặc private profile của từng người trong shared Discord thread.
Raw history chưa có TTL xóa; cancel không xóa dữ liệu. Pending state TTL 30 phút.

Mode mock/llm_only/rag, off/auto/always, Discord auto, JSON/SSE/source/image/feedback giữ hợp đồng tương thích.
Fields mới tùy chọn; legacy/mock không thêm token=None vào payload. UI của TV4 không viết lại.

## Kiểm chứng

- Baseline mới: **740 passed**, 1 warning, 24,06 giây.
- Test mới: **31 case agent/durable**, dùng decision giả, SQLite tạm qua production repository và Qdrant memory.
- Lượt toàn suite cuối **771 passed**, 2 warnings, 22,45 giây; gồm kiểm owner SQL/vector, thêm 31 case.
- Web **40/40**, build/typecheck, Ruff/format (111 file), pip check và OpenAPI đạt.
- UTF-8/121 liên kết local, report/manifest hash và `git diff --check` đạt.
- Legacy provider suite opt-out planner mới rõ ràng; test agent bật true, không gọi fake test là chất lượng live.
- Migration chỉ sinh/kiểm SQL offline; chưa áp thật. Không tải/chạy encoder hoặc gọi DeepSeek/Tavily thật.

Chi tiết và lệnh: [offline report](../testing/2026-11-06_agent-semantic-offline.md).
Live: [preflight report](../testing/2026-11-06_agent-memory-20/README.md), raw JSON giữ 0 attempted turn.
Chưa có đáp án để AI/TV2 review, không fake điểm hoặc trạng thái approved.

## Vận hành tiếp

Settings thật kiểm cuối: agent=true, persistence=memory. Code lưu bền **chưa kích hoạt trên môi trường hiện tại**.
Sau khi sửa hạ tầng, operator xác nhận DB đích, chạy migration 0002 và memory collection setup;
sau đó tự đặt CHAT_PERSISTENCE=postgres và tạo conversation mới. Không tự import RAM cũ hoặc reindex corpus.
Hướng dẫn, graph TD, contract TV4, CLI sync/rebuild và rollback:
[agent-semantic-memory.md](../api/agent-semantic-memory.md).

Runner đã cố định 20 lượt (10 VI/10 EN), tối đa 120 logical model calls, một Search/Extract mỗi lượt,
không retest câu 21; retry SDK=0 trong runner, output directory mới bắt buộc. Phần test thật còn nguyên 20 lượt.
Không chạy migration trên DB đang phục vụ, index corpus, sửa golden/data gốc, `.env` thật hoặc OS.

Chưa xác minh asyncpg/migration thật, recall E5/ANN server, quality/latency/token live, full process restart
hoặc Discord gateway. Không tuyên bố agent hoàn chỉnh, nhớ như ChatGPT hay hết 502.

Tài liệu quyết định cần nhóm đồng bộ riêng nếu duyệt: SRS, architecture, ADR liên quan, system pipeline,
planning và bản sinh. Không tự sửa báo cáo cũ hoặc đánh task Done trong tác vụ này.
