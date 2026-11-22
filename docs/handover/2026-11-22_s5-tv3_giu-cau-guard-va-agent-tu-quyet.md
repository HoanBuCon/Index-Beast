# TV3 · Giữ câu cho Answer Guard, gọt prompt build, lỗi G, bỏ chỗ server quyết định thay Agent

Ngày 21–22/11/2026 · Nhánh `fix/s5-tv3-guard-giu-cau-va-prompt-build` (base `develop` tại `5a18e9c`, sau PR #124). **Chưa commit**; chưa push, chưa có PR.

Liên quan: [handover trước: phân bổ chỉ số, Answer Guard, hạn thời gian](2026-11-21_s5-tv3_build-guard-va-thoi-gian.md) (mục "Hạn chế và việc còn lại" 1–3 và 5 được xử lý ở đây).

## Mục tiêu

1. Không còn câu trả lời hiện một phần rồi báo lỗi; lỗi trình bày được Answer Guard sửa trước khi hiện.
2. Câu build đọc tự nhiên: số chỉ nằm trong bảng, giả định nói ngay dưới bảng.
3. Lỗi ở bước chọn công cụ không làm cả lượt trả 502.
4. Server chỉ giữ guard tất định (schema, provenance, trích dẫn nguyên văn, cấm URL, calculator, ngân sách); mọi quyết định ngữ nghĩa thuộc về Agent. Đây là bước dọn trước khi chuyển sang True Agent (một Agent tự lặp gọi tool).

## Thay đổi chính

### 1. Giữ mọi câu tới khi kiểm xong (`app/rag/generator.py`)

- `_stream_attempt` không còn stream từng đoạn: gom đủ output, kiểm (`validate_answer`), chạy Answer Guard nếu cần, rồi mới đẩy **một chunk** cho SSE.
- Lỗi xảy ra trước khi có chữ hiển thị nên luôn được sinh lại theo `RETRYABLE_REASONS`; không còn "hiện rồi báo lỗi".
- Đổi lại: chữ đầu tiên hiện chậm hơn (bằng thời gian sinh + kiểm cả câu). Bỏ `_check_visible` (validate_answer đã kiểm URL và chỉ số trích dẫn).

### 2. Tên trường nội bộ qua Answer Guard (`generator.py`, `prompts/guard.md`)

- `internal_field_name` không còn là lỗi chặn/sinh lại: `validate_answer` thêm issue `{"kind": "internal_field_name", "fields": [...]}` cho Answer Guard; Guard viết lại câu cho tự nhiên.
- Lưới an toàn cuối: `plain_field_names` thay tên còn sót bằng cụm từ dễ hiểu (vd `player_profile` → "thông tin bạn đưa ra"), trace `internal_field_replaced`.
- `prompts/guard.md` mở rộng cho mọi câu trả lời (không chỉ build). Câu bị từ chối ở validate thì không gửi cho Guard (`guard_request` bị xóa).

### 3. Prompt build và vị trí ghi chú (`prompts/answer.md`, `generator.py`)

- Số 8 chỉ số chỉ nằm trong bảng; đoạn văn nói ưu tiên và lý do, không đọc lại từng số.
- Ghi chú giả định ("Ghi chú cho bảng: giả định class Wretch…; …") đặt **ngay dưới bảng** (`place_under_table`), không còn nối cuối câu. Bảng thiếu hoặc sai vẫn dùng nhãn cũ kèm dòng số đã kiểm.
- Sửa lỗi đếm tổng: `allocation_table` chỉ đọc bảng Markdown, không để dãy chỉ số khởi đầu class trong đoạn văn đè lên bảng (live-11: bảng đúng 229 bị tính thành 85).

### 4. Lỗi G: lỗi model ở bước chọn công cụ (`app/rag/tool_agent.py`)

- `LLMError` ở bước chọn công cụ không còn trả 502 ngay: ghi log `Tool decision model error` (chỉ `reason`, `finish_reason`, số token), báo lại cho Tool Agent kèm cách sửa và cho chọn lại.
- Bị cắt vì hết `max_tokens` (`finish_reason=length`): bước có calculator được nâng trần 2048 → 4096.
- Lỗi lần hai liên tiếp: trả lời từ bằng chứng đã có (`tool_stop=tool_model_error`); chỉ 502 khi chưa có bằng chứng.

### 5. Bỏ chỗ server quyết định thay Agent (`agent.py`, `tool_agent.py`, `pipeline.py`, `prompts/{agent,tools}.md`)

| Mục | Trước | Sau |
|---|---|---|
| Tên gõ sai | `check_name` khớp một tên là server tự sửa câu hỏi/query/profile | `check_name` chỉ trả `candidates` (kèm gợi ý `single_close_match`); Agent đặt trường mới `ToolStep.name` để chọn; server chỉ kiểm tên có trong danh sách rồi áp vào câu hỏi/query/profile. Chưa chọn mà tìm/finish thì nhắc một lần, lần hai dừng (`name_not_chosen`). Nhắc lại tên đã chọn không bị từ chối |
| Fallback câu gốc | Quyết định hỏng bị thay bằng câu gốc (`original_query_fallback`) | Lỗi trả lại cho Agent sửa; `unsupported_number`, `entity_missing_from_query` được thêm lượt sửa; vẫn hỏng thì báo lỗi. Trace bỏ `rewrite_fallback` |
| Web tự chạy | Assessor thiếu query thì server lấy câu gốc tìm web; `followup` chạy không qua Agent | Assessor chỉ gợi ý `suggested_query` trong observation `needs_evidence`; Agent tự quyết |
| Chọn bằng chứng | `rank_fallback` xếp hạng theo plan/batch | Agent không chọn thì `evidence_selection.method = all_evidence` (mọi bằng chứng theo thứ tự tìm được, trong ngân sách context); model viết chọn qua trích dẫn |
| Clarify | Chặn nếu `reason` không thuộc danh sách | Chỉ cần câu hỏi và `missing` |
| Khuyên gameplay | Bảng intent cứng {mechanics, build, gameplay_comparison} | Cờ mới `AgentDecision.gameplay_advice` do Agent đặt (chỉ với `retrieve`) |
| Kiểm giá trị constraint | Bảng key cứng {weapon, starting_class, location} khớp theo tên | Mọi key: khớp chữ hoặc khớp tên |

Giữ lại có chủ đích: tập intent so sánh (`agent.py`) vì chỉ đọc nhãn intent do Agent tự đặt. Chưa làm: chọn đoạn web theo từ khóa (`web_content.py`), đoán ngôn ngữ theo dấu (`pipeline.language`).

## Ảnh hưởng tới web, bot và API (TV4, TV1)

- Schema `ChatRequest`/`ChatResponse` và các event SSE **không đổi**.
- SSE: câu trả lời đến thành **một event `token`** sau khi kiểm xong (trước đây nhiều token). Web nên giữ trạng thái đang tải cho tới token đầu.
- Lỗi sinh câu trả lời giờ luôn xảy ra trước token đầu, nên client nhận **HTTP 502 JSON** thay vì event `error` giữa stream.
- Hạn thời gian giữ nguyên (`CHAT_TIMEOUT_SECONDS=45`, `CHAT_STREAM_TIMEOUT_SECONDS=90`). Discord chưa đo lại.
- Trace dev: `evidence_selection.method` có giá trị mới `all_evidence`/`unselected` (bỏ `rank_fallback`); `name_lookup.status` có `candidates` (bỏ `ambiguous`/`verified` tự động); `verified_name.chosen_by = "agent"`.

## Kiểm tra

- Backend `pytest -q`: **1.155 passed, 20 skipped, 46 deselected**; Ruff check/format đạt; pre-commit đạt. Web/bot không sửa nên không chạy lại.
- Test thật (web SSE, kết quả ở `backend/data/research_runs/2026-11-2x-live-*`, gitignored):

| Lượt | Nội dung | Kết quả |
|---|---|---|
| live-11 (6 câu) | Giữ câu, Guard, prompt build | 5/6 đạt. Guard chạy thật lần đầu (applied) nhưng do báo nhầm tổng, đã sửa. Câu Prisoner 30 + Moonveil 502 ở bước chọn công cụ (lỗi G) |
| live-12 (1 câu) | Chạy lại câu lỗi G | Đạt, 27 giây; lỗi không tái hiện nên nhánh xử lý mới chỉ kiểm offline |
| live-13 (5 câu) | Bỏ server quyết định thay Agent | 5/5 trả lời được, grounded, 17–36 giây. Agent tự chọn "Moonveil" cho "Mooonveil"; lỗi lặp tên ở finish lộ ra và đã sửa (chưa chạy thật lại) |

- **Baseline trước True Agent** (22/11, 10 câu cố định, cùng code nhánh này): 10/10 trả lời được và grounded, p50 17,6 s / p95 36,4 s, trung bình 7,8 lượt gọi model và 3,7 bước công cụ mỗi câu; calculator 1 đạt / 1 lỗi; Answer Guard không chạy. Báo cáo: [docs/testing/2026-11-22_baseline-truoc-true-agent](../testing/2026-11-22_baseline-truoc-true-agent/README.md).
- Ngày 22/11 có thử "calculator mục tiêu mềm" (code tự cân điểm theo ưu tiên, live-14) rồi **rollback toàn bộ** vì đó là rule server quyết thay Agent; nhánh không còn phần này.

## Hạn chế và việc còn lại

1. Answer Guard chưa được kiểm trên một bảng sai thật (lần chạy thật duy nhất là báo nhầm).
2. Calculator: Agent gửi lại đúng số đã bị từ chối nên câu build hay chỉ có bảng tham khảo (live-11 câu 01, live-13 câu 05). Hướng xử lý: trong vòng lặp True Agent, Agent tự sửa từ lỗi; không thêm rule cân số phía server.
3. Câu so sánh (live-13 câu 04): coverage partial nhưng Agent không chọn tìm web; cần theo dõi khi đo baseline.
4. Chưa chạy thật lại câu tên gõ sai sau khi sửa lỗi lặp tên.
5. Discord: chưa có dạng danh sách thay bảng; chưa đo câu build với hạn 45 giây (cần TV4).
6. Bước tiếp theo theo quyết định True Agent của TV3: đo baseline, spike DeepSeek function calling trên nhánh riêng.
