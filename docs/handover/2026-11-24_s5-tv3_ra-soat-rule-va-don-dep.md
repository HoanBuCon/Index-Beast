# TV3 · Rà soát rule cứng còn lại, dọn code chết, prompt và docs cũ

Ngày 24/11/2026 · Nhánh `chore/s5-tv3-ra-soat-rule-va-don-dep` (từ `develop` sau PR #130). **Chưa commit**; chưa push,
chưa có PR. Không gọi API thật (MinhMuc chọn chỉ kiểm offline).

## Phạm vi

1. Rà các chỗ server còn quyết thay Agent. Lần rà 22/11 đã xử lý 5 rule; lần này có 3 điểm mới, MinhMuc duyệt và
   đã sửa (mục dưới).
2. Dọn code và dữ liệu chết, prompt cũ hoặc hỏng, docs mô tả luồng cũ. Chỉ `backend/` và `docs/`, không đụng `bot/`, `web/`.

## Dọn dẹp (không đổi hành vi runtime)

| File | Nội dung |
|---|---|
| `backend/app/rag/context_policy.py` | **Xóa**: `dedup_web` không còn ai gọi từ khi có vòng lặp Agent; bỏ 8 test của nó trong `test_evidence_guards.py` |
| `backend/app/rag/knowledge/gameplay.json`, `backend/scripts/prepare_gameplay_pack.py` | **Xóa**: 14 mục của luồng gameplay cũ, runtime chỉ dùng quy tắc level |
| `backend/app/rag/gameplay_knowledge.py` | Quy tắc level thành hằng số trong code, **cùng ID và payload** (đã so khớp với pack cũ), mỗi lượt một bản sao |
| `backend/app/rag/entity_spelling.py` | Bỏ tham số `contextual_query` và hai nhánh chỉ chạy khi có nó (không nơi nào truyền) |
| `backend/app/rag/pipeline.py` | Bỏ khóa state không ai đọc (`query`, `gameplay`, `name_to_check`, `original_question`) và trace `rewrite_fallback` (luôn `false`) |
| `backend/app/rag/generator.py` | Bỏ tham số `emitted` luôn rỗng của `_retry` (câu trả lời được giữ tới khi kiểm xong) |
| `backend/app/services/answer_media.py`, `prompts/image_selection.md` (mới) | Prompt chọn ảnh tách khỏi code ra file; chuỗi gửi model **giống hệt** trước |
| `prompts/guard.md` | Sửa ví dụ JSON bị gãy: ký tự xuống dòng thật nằm giữa chuỗi thay vì `\n` |
| `prompts/answer.md`, `persona.md`, `format_retry.md`, `gameplay_advice.md` | Bỏ câu cũ: "ảnh chọn sau câu trả lời" (nay song song), "planner", "server-selected language", "Calculate only…" (bước viết không tự tính, số do Agent tính) |
| `backend/scripts/diagnose_gameplay.py`, `diagnose_golden.py` | Nhãn lượt gọi `assessment`/`rewrite` (vai đã gỡ) thành `image_selection`/`answer_guard`; bỏ hash pack đã xóa |
| `backend/tests/unit/test_live_chat.py` | Bỏ bộ giả lập trả lời cho vai "decision component"/"tool planner" (prompt hiện tại không còn) |
| `.env.example` | Bỏ `LLM_JUDGE_MODEL`, `WEB_FALLBACK_ENABLED` (không có code đọc); `ADMIN_TOKEN` sang mục "Trang quản trị" |
| `backend/app/rag/README.md` | Thêm mục **Hiện trạng** ở đầu (luồng, bảng guard server còn giữ, danh sách prompt); sửa sơ đồ và các câu mô tả rewrite, heuristic đại từ, câu tĩnh khi thiếu nguồn |
| `docs/01_TECHSTACK.md`, `02_SRS.md`, `api/langgraph-memory.md`, `indexbeast-system-pipeline.md` | Sửa dòng mô tả rewrite, Tool planner, calculator, gói gameplay |
| `docs/api/agent-semantic-memory.md` | Bỏ cờ `CHAT_AGENT_ENABLED`, sửa phần ngân sách; migration hiện là 0005 |
| `docs/api/evidence-media-build.md` | Banner lịch sử + mô tả chọn ảnh song song hiện nay |
| `docs/api/gameplay-clarification-tv4.md`, `api/web-search-tv4.md`, `ke-hoach-on-dinh-indexbeast.md` | Banner lịch sử trỏ về ADR 006 |

Không sửa: `docs/testing/`, `docs/handover/` cũ, `03_SPRINT_PLAN.md`, ADR 006 (bản ghi lịch sử). Cache `__pycache__` của
module đã gỡ (`agent`, `tool_agent`, `rewrite`, `build_data`) không nằm trong git, có thể tự xóa.

## Trace đổi khóa (báo TV1)

- Bỏ: `rewrite_fallback` (luôn `false`), `request_kind` (dùng `agent.intent`). Thêm cho đường `reply`/`ask_user`: `internal_field_replaced`. Kết quả tool `check_name` trong `agent` không còn `single_close_match`. Phase `assessment`/`rewrite` chỉ có trong output script chẩn đoán, không có
  trong trace API.

## Kiểm tra đã chạy

- `pytest tests/unit`: **939 passed**, 20 skipped (trước 944; bớt 8 test của `dedup_web`, thêm 3 test cho 3 mục sửa).
- `ruff check`, `ruff format --check`, `scripts.export_openapi --check`, pre-commit trên mọi file đổi: đạt.
- Không chạy thật. Phần đổi prompt (true_agent, guard, answer, persona, format_retry, gameplay_advice) chưa được đo trên model.

## Sửa 3 chỗ server còn quyết thay Agent (MinhMuc duyệt "sửa cả 3", 24/11)

1. **`check_name` không còn chấm chính tả**: trả tiêu đề các kết quả tìm được (khử trùng, theo thứ tự retrieval,
   tối đa 8) kèm bản xem trước; bỏ `single_close_match`. Agent tự chọn tên người chơi muốn nói (prompt và mô tả tool
   đã nói rõ đây không phải kết luận chính tả). Xóa `app/rag/entity_spelling.py` (~70 dòng heuristic) và các hàm chỉ
   nó dùng trong `matching.py` (`folded`, `numbers_in`, `preserves_numbers`).
2. **AG-2**: văn bản `reply`/`ask_user` đi thẳng ra người chơi nên giờ qua cùng lưới an toàn với câu trả lời RAG
   (`plain_field_names`): tên trường nội bộ được thay bằng chữ thường, trace `internal_field_replaced`; không gọi thêm
   model. `true_agent.md` dặn Agent không nêu tên tool, trường hay cờ trong hai văn bản này.
3. **Bỏ `trace.request_kind`** (trùng `trace.agent.intent`).

Test mới trong `test_true_agent.py`: `check_name` trả mọi tiêu đề tìm được; `reply` và `ask_user` không lộ
`player_profile`. Chưa chạy thật: câu viết sai chính tả (mục 1) và câu `reply` (mục 2) nên đo ở lượt chạy thật tới.
Lưới an toàn mục 2 chỉ bắt các tên trong `INTERNAL_FIELD` (`player_profile`, `agent_results`, `quote_id(s)`,
`evidence_units`); từ như `insufficient` chỉ được prompt chặn.

Giữ nguyên (đã xét): guard nguồn của `set_conditions`, corpus policy, web `always`, nhắc chọn evidence một lần, ngân
sách và lượt `finish` bắt buộc, kiểm trích dẫn, Answer Guard, quy tắc level dựng sẵn, lọc ký ức trong thread
Discord, lọc ứng viên ảnh theo metadata (bước chọn ảnh vẫn do model), ưu tiên trích Fextralife trong `answer.md`
(quyết định của nhóm).

## Việc còn lại

- Chạy thật vài câu viết sai chính tả (`check_name`) và câu `reply`/`ask_user` khi MinhMuc cho gọi API.
- Commit, push, PR về `develop` (MinhMuc tự làm).
