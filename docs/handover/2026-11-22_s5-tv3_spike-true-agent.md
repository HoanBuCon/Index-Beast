# TV3 · Spike True Agent bằng DeepSeek function calling

Ngày 22/11/2026 · Nhánh `feature/s5-tv3-true-agent-spike` (tách từ `origin/develop` tại `56d6400`, sau PR #125). **Chưa commit**; chưa push, chưa có PR.

## Mục tiêu

Giai đoạn 1 của hướng True Agent (một Agent tự lặp gọi tool thay cho pipeline nhiều vai Agent decision → Tool planner → Assessor → Generator): kiểm DeepSeek native tool calling có chạy ổn định với tool thật của IndexBeast không, và so với baseline cùng ngày (10 câu cố định).

## Thay đổi

| File | Nội dung |
|---|---|
| `backend/app/rag/true_agent.py` (mới) | `run_true_agent(pipe, req, variant=...)`: vòng lặp `ChatDeepSeek.bind_tools` (`tool_choice=auto`, non-thinking, temperature 0). Tool: `search_corpus`, `search_web`, `check_name` (chỉ trả ứng viên), `open_evidence`, `calculator` (dùng `build_data.check`), `ask_user`, `reply`; kết thúc bằng `finish` (biến thể `generator`: Generator + Answer Guard hiện có) hoặc `final_answer` (biến thể `final_answer`: Agent tự viết, `validate_answer` kiểm, lỗi trả lại cho Agent). Lỗi tool, tham số sai và lệnh gọi có JSON hỏng (`invalid_tool_calls`) đều trả về cho Agent như kết quả tool. Ngân sách: 10 lượt gọi model, 10 tool, `CHAT_PREPARE_TIMEOUT_SECONDS`. Level/class/weapon đưa vào calculator phải là lời người chơi |
| `backend/app/rag/prompts/true_agent.md` (mới) | Prompt hệ thống của Agent (vai trò, tool, build, hỏi lại, ngân sách); biến thể `final_answer` nối thêm luật viết và `answer.md` |
| `backend/tests/unit/test_true_agent.py` (mới) | 5 test offline với model tool calling giả: danh sách tool theo biến thể, biến thể A, biến thể B có lần bị từ chối rồi sửa, calculator chỉ nhận lời người chơi, lệnh gọi JSON hỏng được trả lời |
| `backend/scripts/spike_true_agent.py` (mới) | Chạy thật một manifest với một biến thể (tốn phí) |
| `docs/testing/2026-11-22_spike-true-agent/` (mới) | Báo cáo so baseline, `summary.json`, `manifest.json` |

**Không đổi**: API, pipeline đang chạy (`agent.py`, `tool_agent.py`, `pipeline.py`), web, bot. Không thêm cờ cấu hình. Prototype dùng lại `ChatPipeline._scope/_context/_prompt` (hàm nội bộ) nên chỉ hợp cho spike.

## Kiểm tra

- Backend `pytest -q`: **1.160 passed, 20 skipped, 46 deselected** (gồm 5 test `test_true_agent.py`); Ruff, pre-commit đạt.
- Chạy thật (đã chạy, 25 câu tính cả thử và chạy lại): chi tiết ở [báo cáo spike](../testing/2026-11-22_spike-true-agent/README.md).

| | Baseline | A: Agent + Generator | B: Agent tự viết |
|---|---|---|---|
| Trả lời được / grounded | 10/10 | 10/10 | 10/10 |
| p50 / p95 | 17,6 / 36,4 s | 11,5 / 37,2 s | 14,2 / 25,4 s |
| Lượt gọi model / câu | 7,8 | 4,3 | 5,8 |
| Calculator đạt | 1/2 | 2/2 | 2/2 |
| Token đầu vào / câu | chưa đo | ~36 nghìn | ~82 nghìn |

- Sự cố khi chạy: lần đầu 3 câu build lỗi HTTP 400 vì không trả lời `invalid_tool_calls`; đã sửa, thêm test, chạy lại đúng 3 câu đó (đạt).
- Baseline đo qua API SSE có chọn ảnh; spike gọi thẳng, không chọn ảnh, không lưu hội thoại: độ trễ chưa so ngang hoàn toàn.

## Đề xuất và việc còn lại

1. Chọn biến thể **A** cho GĐ2 (ít lượt gọi và token nhất, giữ hợp đồng trích dẫn/stream/Answer Guard).
2. Trước khi nối API: rút gọn kết quả tool đưa lại cho Agent (token), memory và clarification thật (`Clarification`, player state), chọn ảnh, stream; đo lại cùng bộ câu qua API, có ghi token cho cả baseline.
3. GĐ2 sẽ thay `agent.py` + `tool_agent.py` + assessor bằng vòng lặp này và viết lại nhiều test; cần ADR trong repo trước khi xóa pipeline cũ.
4. Chưa thử: hội thoại nhiều lượt, Discord (hạn 45 s), câu cần web (Agent không dùng `search_web` lần nào trong 10 câu).
