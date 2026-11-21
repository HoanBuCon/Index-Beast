# TV3 · True Agent GĐ2: một vòng lặp Agent thay Agent decision, Tool Agent và Assessor

Ngày 22/11/2026 · Nhánh `feature/s5-tv3-true-agent-gd2` (tách từ `origin/develop` tại `cb12859`). **Chưa commit**; chưa push, chưa có PR. Quyết định: [ADR 006](../adr/006-true-agent.md). Trước đó: [spike GĐ1](2026-11-22_s5-tv3_spike-true-agent.md).

## Mục tiêu

Thay pipeline nhiều vai (Agent decision → Tool planner → Assessor, mỗi vai một lượt gọi LLM) bằng một vòng lặp Agent dùng native tool calling, nối vào API thật; giữ Generator, Answer Guard, chọn ảnh, hợp đồng API/SSE. Server không quyết định ngữ nghĩa thay Agent.

## Thay đổi

### Code (`backend/app/rag/`)

| File | Nội dung |
|---|---|
| `true_agent.py` (viết lại) | `run_agent(pipe, state)`: vòng lặp `ChatDeepSeek.bind_tools`. Tool `search_corpus`, `search_web`, `check_name` (chỉ trả ứng viên), `open_evidence`, `set_conditions`, `calculator`, `ask_user`, `reply`, `finish`. Kết quả tool rút gọn (8 kết quả, 320 ký tự). Mọi lỗi (tham số sai, JSON hỏng, giá trị không phải lời người chơi, calculator từ chối, web lỗi) trả lại cho Agent |
| `prompts/true_agent.md` (viết lại) | Prompt duy nhất của Agent |
| `pipeline.py` | Node `agent` thay `agent_decision` + `tool_agent`; bỏ import và phần payload `task_plan` |
| `budget.py` (mới) | `spend()` (ngân sách lượt gọi) tách khỏi `agent.py` |
| `web_search.py` | Chỉ còn `merge_evidence` (bỏ `assess`, `Assessment`) |
| `entity_spelling.py` | Bỏ `correct_name` (server không tự sửa tên) |
| **Xóa** | `agent.py`, `tool_agent.py`, `task_plan.py`, prompt `agent.md`, `tools.md`, `assess.md` (prompt chết) |

Khác: `app/services/chat.py` (log hết hạn ghi `agent_steps`), `scripts/diagnose_golden.py` (`CapturedLLM.model`), `scripts/diagnose_agent_memory.py`, `core/config.py`, `.env.example`, `docker-compose.yml` (bỏ biến chết). Script mới `scripts/run_live_manifest.py` (đo thật một manifest qua API); xóa `scripts/spike_true_agent.py`.

### Hành vi đáng chú ý

- **Working state giữ lõi**: điều kiện người chơi (level, class, vũ khí, mục tiêu…) do Agent ghi bằng `set_conditions`, server kiểm giá trị có trong lời người dùng hiện tại, câu gốc đang hỏi lại hoặc ký ức được dẫn (ký ức dẫn bằng ID dòng được quy về `source_id` của tin nhắn). Điều kiện giữ qua các lượt tới khi Agent thay hoặc `retire`. Clarification giữ ID, hạn 30 phút, trần `CHAT_CLARIFICATION_MAX_ROUNDS` (quá trần thì `ask_user` không được đưa cho Agent). **Bỏ task_plan/subgoals.**
- `reply` với `end_task` xóa working state (hủy yêu cầu); `unrelated` ghi intent `out_of_scope` (ký ức chủ đề không lưu).
- Kho corpus lỗi mà không có bằng chứng: `UnavailableError` như trước; Agent không gọi được tool nào hợp lệ: `UpstreamError`.
- Chính sách web `always`: `finish` bị từ chối tới khi đã gọi `search_web`.

### Cấu hình

Bỏ `CHAT_TOOL_STEPS`, `CHAT_TOOL_QUERIES`, `CHAT_COVERAGE_STEPS` (Settings dùng `extra="ignore"` nên `.env` cũ vẫn chạy). Ngân sách: `CHAT_AGENT_MAX_CALLS` (web off/always), `CHAT_COVERAGE_MAX_CALLS` (web auto), `CHAT_PREPARE_TIMEOUT_SECONDS`; calculator được thử tối đa `CHAT_CALCULATOR_MAX_FAILURES` + 1 lần.

### Mục 13, 14 (cùng nhánh, 22/11)

- **Đoạn web (mục 13)**: `web_content.select_excerpts` không còn chấm điểm theo từ khóa và bỏ bảng stopword; trang được chia khối (~3.500 ký tự, giữ tiêu đề mục, không lặp tiêu đề trong khối) theo đúng thứ tự trang, tối đa 6 khối/trang (ngân sách, không xếp hạng). `adapters/tavily.py` lấy mọi khối đó (trước đây 3 khối điểm cao nhất), `section` ghi `Web excerpt n/N`. `search_web` trả cho Agent kết quả gom theo trang (`pages[].blocks[]`, xem trước 200 ký tự); Agent tự mở khối bằng `open_evidence`.
- **Ngôn ngữ (mục 14)**: bỏ `pipeline.language()` (đoán theo dấu). Ngôn ngữ = lựa chọn của người dùng; nếu `auto` thì ngôn ngữ Agent khai báo ở `finish`/`ask_user`/`reply`; Agent chưa khai báo thì ngôn ngữ của working state, cuối cùng tiếng Việt.
- Test thật 4 câu mới (2 web, 1 tiếng Anh, 1 tiếng Việt không dấu): 4/4 grounded, câu không dấu trả lời tiếng Việt ([báo cáo](../testing/2026-11-22_true-agent-gd2/README.md)).

### Rà soát sau GĐ2 và câu hỏi về chính cuộc trò chuyện (22/11)

- **Lỗi**: hỏi "Câu hỏi trước của tôi là gì?" thì IndexBeast trả lời lạc đề. **Nguyên nhân**: Agent chỉ thấy 2 câu hỏi trước của người chơi (làm "ký ức", prompt dặn không phải bằng chứng), không thấy câu trả lời của trợ lý, và `reply` chỉ được mô tả cho chào hỏi/ngoài phạm vi, nên Agent đi tìm wiki rồi `finish` và Generator viết về game. **Sửa**: `pipeline._recent_turns` đưa cho Agent các lượt gần nhất (cả câu hỏi lẫn câu trả lời, ≤800 ký tự/lượt, trong `CHAT_HISTORY_MESSAGES`/`CHAT_HISTORY_CHARS`) dưới khóa `recent_turns`; `reply` có `about_conversation` (intent `conversation`, không lưu làm ký ức chủ đề trong `memory_repository.py`); prompt hướng dẫn trả lời câu về hội thoại từ `recent_turns` và dùng nó để hiểu câu nhắc lại lượt trước. Lượt cũ không bao giờ là bằng chứng về game.
- **Code chết đã xóa**: `generator.grounded_stream_prefix`, `generator.answer_prefix` + `StreamPrefixError` + `output.stream_body_prefix` (không còn giải mã stream từng đoạn), `build_data.BuildCache`, `build_data.stat_numbers_in`, `gameplay_knowledge.trusted_rule_kind`; nhánh `coverage_checks`/`answer_coverage`/`verified_name` trong `pipeline.py`; đoạn prompt `task_plan` và `evidence_coverage` trong `answer.md` (đầu vào không còn tồn tại); test của các phần này.
- **Rà soát server làm hộ Agent**: không còn chỗ quyết định ngữ nghĩa. Giữ có lý do (guard tất định): lọc ứng viên ảnh theo liên kết nguồn (chọn ảnh vẫn do model), gộp đoạn web trùng hệt, retriever hybrid/rerank, `check_name` chỉ đề xuất ứng viên, thêm nguồn luật vào context khi có bảng đã kiểm, câu tĩnh khi không có bằng chứng, chính sách web `always`, Discord ép `auto`, fallback `all_evidence` (thứ tự tìm được) khi Agent không chọn bằng chứng.
- **Để thành viên khác duyệt** (thuộc pipeline dữ liệu TV1/TV2, không xóa): chỉ test dùng `core/db/repositories.py` (`create_conversation`, `add_message`, `recent_messages`, `message_exists`, `add_feedback`, `upsert_document`, `replace_chunks`, `start_job`, `finish_job`), `core/text/chunking.chunk_section`, `core/text/html_clean.clean_html`, `core/text/lore_policy.context_groups`/`editorial_template`, `core/text/quest_stages.stage_locations`; không ai dùng: model `core/db/models.Entity`, `core/text/quest_stages.QUEST_SECTION`, `core/text/structured_tables.row_metadata`.
- Test thật 4 câu mới (chế độ RAM): 4/4 ([báo cáo](../testing/2026-11-22_true-agent-gd2/README.md)).
- **Chế độ PostgreSQL (lần đầu chạy thật, 22/11)**: DB local nâng 0002 → 0005, `memory_admin setup --apply`, `.env` máy dev đổi `CHAT_PERSISTENCE=postgres`. 2 hội thoại mới, restart app giữa hai lượt: 2/2 đúng (hỏi lại câu trước, hiểu "phép đó"); token và ký ức chủ đề lưu đúng.

### Build linh động: trả lời trước với giả định rõ ràng (22/11)

- **Vấn đề**: xin build mà không nêu level/class thì IndexBeast hỏi lại. Nguồn: prompt Agent dặn hỏi level khi muốn số, calculator chỉ nhận level do người chơi nêu, prompt viết câu chỉ cho định tính khi thiếu level.
- **Sửa**: `set_conditions` nhận nguồn `assumption` (Agent tự chọn giả định theo ngữ cảnh). Server: giả định không được đè điều kiện người chơi đã nêu, **không lưu vào working state** (nên không thành ký ức "fact"), chỉ dùng cho lượt này qua `state["turn_profile"]`; hồ sơ có khóa `assumed` (vd `level`), calculator vẫn kiểm đủ. Ghi chú dưới bảng tự nêu "giả định level 150 vì bạn chưa nêu"; `answer.md` dặn mời người chơi cho số thật một lần. Agent chỉ hỏi level khi người chơi đòi bảng chính xác cho nhân vật của họ.
- Trace: `agent.steps[]` có thêm `error` (thông báo từ chối của server, ≤160 ký tự) và `fields` khi bước bị từ chối.
- Test thật 4 câu build mới: không câu nào bị hỏi lại sai; 2/4 có bảng đã kiểm, 2/4 hết ngân sách vì tìm kiếm quá nhiều trước khi chia điểm ([báo cáo](../testing/2026-11-22_true-agent-gd2/README.md)).

### Agent tự tính bằng Python, bỏ calculator và kiểm tra build cứng (22/11)

- **Lý do** (MinhMuc): mỗi lần test lại ra lỗi mới ở calculator; gốc là rule cứng phía server (schema `build_data`, nhãn/quote bắt buộc cho từng số, LLM phải tự cộng cho khớp).
- **Thay**: tool `run_python` (`app/rag/python_sandbox.py`): Agent tự viết code chia điểm và tự kiểm (tổng = level + 79, sàn class, yêu cầu vũ khí lấy từ nguồn đã mở), đưa kết quả qua `finish.results` → Generator nhận `agent_results`. Sandbox: kiểm cú pháp chỉ cho tập con Python (không import, không `_…`, không `format`/`eval`/`exec`/`open`…), builtins giới hạn, tiến trình con `-I -S` môi trường rỗng, timeout 3 s, đầu ra ≤4.000 ký tự, giới hạn bộ nhớ 256 MB trên POSIX. **Chưa phải sandbox cấp hệ điều hành**: production nên chạy trong container riêng không mạng.
- **Xóa**: `app/rag/build_data.py` (calculator, schema, kiểm nhãn), `checked_build` (Prepared, pipeline, generator), kiểm bảng chỉ số và ghi chú giả định do server viết, issue bảng của Answer Guard, `build_allocation`, cấu hình `CHAT_CALCULATOR_MAX_FAILURES`; `level_rule` chuyển sang `gameplay_knowledge.py` và được đưa sẵn cho Agent làm nguồn (`built_in_sources`). Prompt `true_agent.md`, `answer.md`, `guard.md`, `gameplay_advice.md` viết lại tương ứng. Test: xóa `test_build_data.py`, thêm `test_python_sandbox.py` (16 test, có chặn code độc) và `test_answer_guard.py`.
- **Rủi ro đã chấp nhận**: server không kiểm lại số build; Agent quên chạy code hoặc tính sai thì số sai tới người chơi.
- Test thật 4 câu build mới: 4/4 có bảng, tổng và sàn class đúng khi tính lại tay ([báo cáo](../testing/2026-11-22_true-agent-gd2/README.md)).
- **Rà soát toàn bộ rule cứng còn lại** (27 mục): giữ 22 (guard nguồn, bảo mật, quyền riêng tư, ngân sách), MinhMuc duyệt thay 5:
  1. Hai evidence cùng nguồn: gộp quote thay vì bắt sinh lại (bỏ lý do `duplicate_evidence_index`).
  2. Lời khuyên gameplay (`advisory`) được kèm `recommendation`/`limitation`; vẫn cấm trích dẫn, URL và vẫn cần cờ `gameplay_advice` của Agent.
  3. Bỏ câu tĩnh "Mình chưa có đủ thông tin…" của server: không có bằng chứng thì bước viết trả `insufficient` (thêm 1 lượt gọi model cho trường hợp này).
  4. Bỏ fallback `all_evidence`: `finish` rỗng khi đã tìm được bằng chứng thì server nhắc Agent chọn một lần; vẫn rỗng hoặc hết budget thì không có bằng chứng. Trace luôn `evidence_selection.method = model`.
  5. Discord không còn bị ép web `auto`: dùng giá trị client gửi (bot hiện gửi `auto`, hành vi không đổi).

## Ảnh hưởng tới web, bot và thành viên khác

- API JSON/SSE **không đổi** (OpenAPI `--check` đạt).
- Trace dev đổi: `trace.agent` có `steps` (tool, status, ms), `usage` (token), `intent`, `action`; `model_calls` ghi `agent`; `graph_nodes`/`node_ms` có `agent` thay `agent_decision`/`tool_agent`; bỏ `tool_actions`, `coverage_checks`, `task_plan`, `rewrite_fallback`.
- **Đã cập nhật hộ TV1** hai script đọc trace: `scripts/llm_cost.py` (đếm lần tìm web từ `agent.steps` tool `search_web`, vẫn đọc trace cũ) và `scripts/trace_latency.py` (bước `agent` từ `node_ms.agent`, `tool:<tool>` từ `agent.steps[].ms`, vẫn đọc trace cũ); thêm test. Trang admin trên web không đọc các khóa này nên không phải sửa. Nhờ TV1 review.
- `token_usage()` giờ cộng cả token của Agent nên `tokens_in/out` lưu trong DB tăng (đúng hơn).

## Kiểm tra

- Backend `pytest -q` (sau cả mục 13, 14, rà soát cuối, build linh động và `run_python`): **932 passed, 20 skipped, 46 deselected** (bỏ test calculator, thêm test sandbox) (bỏ khoảng 170 test chỉ kiểm dây chuyền cũ: `test_tool_agent.py`, `test_adaptive_agent.py`, `test_superseded_conditions.py`, `test_progress_clarification.py`, `test_agent_media_regressions.py`, các test `assess` và decision schema; hành vi còn giá trị được viết lại trong `test_true_agent.py`, `test_agent_durable.py`, `test_build_data.py`, `test_reranker_wiring.py`, `test_gameplay_multi_source.py`). Ruff, pre-commit, OpenAPI check đạt. Fixture `golden_guard_replays.json` bỏ phần `assessments`, `rewrites` không còn dùng.
- Test thật qua API SSE (đã chạy, 14 câu + 2 thử): [báo cáo](../testing/2026-11-22_true-agent-gd2/README.md).

| | Baseline | GĐ2 |
|---|---|---|
| 10 câu baseline trả lời được / grounded | 10/10 | 10/10 |
| p50 / p95 | 17,6 / 36,4 s | 16,6 / 29,1 s |
| Lượt gọi model / câu | 7,8 | 6,0 |
| Calculator đạt | 1/2 | 2/2 |
| 4 câu mới (sửa level, trả lời hỏi lại, 2 câu web) | — | 4/4 |

## Hạn chế và việc còn lại

1. Câu build ~35 s, sát hạn 45 s của JSON/Discord; token Agent ~23 nghìn/câu (build tới ~42 nghìn). Chưa đo kênh Discord.
2. Answer Guard vẫn chưa được kiểm trên một bảng sai thật.
3. Chưa chấm chất lượng theo golden set; chưa có hội thoại hơn 2 lượt.
4. ~~Server làm thay Agent còn mục 13, 14~~: đã xử lý cùng nhánh (xem mục dưới).
5. Code chết còn sót từ trước: `gameplay_knowledge.trusted_rule_kind`.
6. Tài liệu lịch sử (`docs/api/bounded-tool-agent.md`, `agent-semantic-memory.md`, handover cũ) giữ nguyên nội dung, đã thêm ghi chú trỏ sang ADR 006.
