# ADR 006 Một vòng lặp Agent (True Agent) thay pipeline nhiều vai

Ngày: 2026-11-22. Trạng thái: **Chấp nhận** (TV3 MinhMuc duyệt hướng 22/11/2026, chọn biến thể A sau spike). Cài đặt trên nhánh `feature/s5-tv3-true-agent-gd2`.

## Bối cảnh

- Đến 21/11, mỗi lượt chat RAG là một pipeline nhiều vai cố định, mỗi vai một lượt gọi LLM với prompt và schema JSON riêng: Agent decision (`agent.py`, `agent.md`) → Tool planner lặp (`tool_agent.py`, `tools.md`) → Assessor (`web_search.assess`, `assess.md`) → Generator (`answer.md`) → Answer Guard → chọn ảnh.
- Baseline 22/11 (10 câu cố định qua API): p50 17,6 s, p95 36,4 s, 7,8 lượt gọi model/câu, trong đó gần một nửa là `tool_decision`; calculator đạt 1/2 câu build.
- Phần lớn chỗ "server làm hộ Agent" là keo nối giữa các vai (fallback câu gốc, tự chạy web theo assessor, tự chọn bằng chứng, chặn clarify theo lý do, bảng intent). Một phần đã gỡ ngày 21–22/11; gốc rễ là việc chia vai làm mất ngữ cảnh giữa các lượt gọi.
- Miền hẹp (Elden Ring), khoảng 9 tool, hạn 45 s (JSON/Discord) và 90 s (web SSE), đồ án môn học.

## Quyết định

1. Mỗi lượt RAG được chuẩn bị bởi **một vòng lặp Agent** dùng native tool calling của DeepSeek qua LangChain (`ChatDeepSeek.bind_tools`, `tool_choice=auto`, non-thinking): `app/rag/true_agent.py`, prompt `prompts/true_agent.md`. Node `agent` thay hai node `agent_decision` + `tool_agent` trong `ChatPipeline.prepare_graph`.
2. Tool: `search_corpus`, `search_web` (theo chính sách web), `check_name` (chỉ trả ứng viên), `open_evidence`, `set_conditions` (điều kiện người chơi, hoặc giả định có nhãn), `run_python` (Agent tự tính trong sandbox; thay calculator từ 22/11), `ask_user` (Clarification có ID, hạn 30 phút, trần số vòng), `reply` (chào hỏi, hủy, ngoài phạm vi), `finish` (yêu cầu độc lập, intent, ngôn ngữ, bằng chứng, cờ `gameplay_advice`).
3. **Agent quyết định mọi thứ ngữ nghĩa.** Server chỉ chạy tool, kiểm tất định và giữ ngân sách: chính sách corpus, giá trị điều kiện phải có trong lời người dùng hoặc ký ức được dẫn, sandbox `run_python`, chính sách web, số lượt gọi và thời gian. Mọi lần từ chối trả lại cho Agent như kết quả tool để nó tự sửa; lệnh gọi có JSON hỏng cũng được trả lời.
4. **Biến thể A**: Agent kết thúc bằng `finish`; Generator + Answer Guard hiện có viết và kiểm câu trả lời (hợp đồng trích dẫn, giữ câu tới khi kiểm xong, stream một token). Không chọn biến thể Agent tự viết `final_answer`.
5. Giữ lõi working state (điều kiện có kiểm nguồn, Clarification, ký ức ứng viên), **bỏ task_plan/subgoals**. Một luồng duy nhất, không cờ. Xóa `agent.py`, `tool_agent.py`, `task_plan.py`, `web_search.assess` và prompt `agent.md`, `tools.md`, `assess.md`.

## Phương án đã cân nhắc

| Phương án | Lý do không chọn |
|---|---|
| Giữ pipeline nhiều vai, chỉ bỏ dần rule | Vẫn 7–12 lượt gọi/câu; mỗi lần bàn giao giữa các vai mất ngữ cảnh nên lại cần keo phía server |
| Multi-agent (supervisor + agent lore/build/route) | Thừa với một miền và ít tool; thêm lượt gọi, độ trễ, lỗi phối hợp; dễ vượt 45 s |
| Agent tự viết `final_answer` (biến thể B) | Spike: token đầu vào ~2,3 lần A, 6/10 câu phải viết lại vì sai trích dẫn |
| Calculator tự cân số theo ưu tiên | Thử 22/11 rồi rollback: vẫn là server chọn số thay Agent |

## Hệ quả

- Đo qua API (10 câu baseline): 10/10 grounded, p50 16,6 s, p95 29,1 s (baseline 36,4 s), 6,0 lượt gọi model/câu (baseline 7,8), calculator 2/2. Thêm 4 câu (sửa level giữa hội thoại, trả lời câu hỏi lại, 2 câu web): 4/4. Chi tiết: [docs/testing/2026-11-22_true-agent-gd2](../testing/2026-11-22_true-agent-gd2/README.md).
- Token đầu vào của Agent ~23 nghìn/câu (câu build tới ~42 nghìn) vì ngữ cảnh vòng lặp dài dần; kết quả tool đã rút gọn (8 kết quả, 320 ký tự/kết quả).
- Trace đổi: `trace.agent` có `steps`, `usage`, `intent`; `model_calls` ghi `agent`; bỏ `tool_actions`, `coverage_checks`, `task_plan`, `rewrite_fallback`. API JSON/SSE không đổi.
- Bỏ cấu hình `CHAT_TOOL_STEPS`, `CHAT_TOOL_QUERIES`, `CHAT_COVERAGE_STEPS`, `CHAT_CALCULATOR_MAX_FAILURES`. Ngân sách: `CHAT_AGENT_MAX_CALLS` (web off/always), `CHAT_COVERAGE_MAX_CALLS` (web auto), `CHAT_PREPARE_TIMEOUT_SECONDS`.
- 23/11 (đo lại sau `run_python`): ngân sách đếm **lượt gọi model**, không đếm số tool trong một lượt (bỏ trần bước ngầm). Agent biết tổng lượt (`model_calls` trong input) và được nhắc khi còn ≤ 3 lượt. Khi hết lượt hoặc hết thời gian, lượt cuối chỉ đưa tool `finish` (`tool_choice`), nên Agent luôn tự chọn evidence và ghi kết quả đã tính; trước đây hết ngân sách là mất hết những gì đã tìm. Trace có `agent.forced_finish`.
- 22/11 (sau): calculator viết cứng và mọi kiểm tra build phía server bị bỏ; Agent tự tính và tự kiểm bằng `run_python` (`app/rag/python_sandbox.py`, sandbox theo tập con Python). Server không kiểm lại số build: đánh đổi có chủ đích để bớt rule cứng.
- 22/11 (rà soát rule cứng): bỏ fallback `all_evidence` (Agent được nhắc chọn bằng chứng một lần), câu tĩnh "chưa có đủ thông tin" (bước viết trả `insufficient`), ép Discord web `auto`, lỗi `duplicate_evidence_index` (gộp quote) và các tổ hợp cấm của `advisory`. Giữ các guard nguồn, bảo mật, quyền riêng tư và ngân sách.

## Xem lại khi

- Độ trễ câu build vượt hạn Discord 45 s thường xuyên, hoặc token/chi phí vượt ngân sách.
- DeepSeek đổi hành vi tool calling (JSON tham số hỏng nhiều, bỏ qua tool).
- Dự án thêm miền mới cần tool và ngữ cảnh rất khác nhau (lúc đó mới cân nhắc tách agent).
