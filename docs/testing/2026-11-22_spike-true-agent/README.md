# Spike True Agent (DeepSeek function calling) so với baseline — 22/11/2026

TV3 MinhMuc · Nhánh `feature/s5-tv3-true-agent-spike` (từ `origin/develop` `56d6400`, chưa commit). Prototype `backend/app/rag/true_agent.py`, **chưa nối vào API**. Baseline so sánh: `docs/testing/2026-11-22_baseline-truoc-true-agent/` (cùng 10 câu, cùng ngày).

## Đã chạy gì

- Một vòng lặp native tool calling (`ChatDeepSeek.bind_tools`, `tool_choice=auto`, non-thinking, temperature 0) với các tool: `search_corpus`, `search_web`, `check_name` (chỉ trả ứng viên), `open_evidence`, `calculator` (dùng `build_data.check` hiện có), `ask_user`, `reply`, và kết thúc bằng:
  - **A (`generator`)**: `finish(evidence_ids, request, answer_language, gameplay_advice)` → `_context`/`_prompt` + Generator + Answer Guard hiện có.
  - **B (`final_answer`)**: Agent tự viết câu trả lời; `validate_answer` kiểm trích dẫn/quote, lỗi hoặc issue trình bày trả lại cho Agent sửa.
- Server chỉ chạy tool, kiểm (chính sách corpus, nguồn, phép tính, giá trị level/class/weapon phải là lời người chơi) và giữ ngân sách (10 lượt gọi, 10 tool, `CHAT_PREPARE_TIMEOUT_SECONDS`). Lỗi trả về cho Agent như kết quả tool.
- Chạy thật 10 câu baseline ([manifest.json](manifest.json)) cho mỗi biến thể, gọi thẳng prototype qua pipeline của app thật (`.env`, lifespan, PostgreSQL/Qdrant/Redis, DeepSeek, Jina, Tavily), `web_search=auto`. Trước đó thử 2 câu (BL-03 với A, BL-05 với B).
- Lần chạy đầu: A 9/10, B 8/10. Ba câu build lỗi HTTP 400 của DeepSeek vì prototype không trả lời lệnh gọi tool có JSON tham số hỏng (`invalid_tool_calls`). Đã sửa (trả lỗi cho Agent gửi lại) + test, **chạy lại đúng 3 câu đó** (A: BL-06; B: BL-05, BL-06). Số liệu dưới đây gộp lần chạy lại; tổng cộng 2 + 20 + 3 = 25 câu đã gọi thật.

## Kết quả

| Chỉ số | Baseline (pipeline nhiều vai) | A: Agent + Generator | B: Agent tự viết |
|---|---|---|---|
| Trả lời được / grounded | 10/10 / 10/10 | 10/10 / 10/10 | 10/10 / 10/10 |
| p50 / p95 / max | 17,6 / 36,4 / 36,6 s | **11,5** / 37,2 / 38,0 s | 14,2 / **25,4** / 27,2 s |
| Trung bình | 20,3 s | 15,5 s | 15,2 s |
| Lượt gọi model / câu (tb, max) | 7,8, 11 | **4,3**, 7 | 5,8, 10 |
| Lượt gọi tool / câu | 3,7 | 4,2 | 5,9 |
| Calculator đạt (2 câu build) | 1/2 | **2/2** | **2/2** |
| Token đầu vào / câu (tb, max) | chưa đo | 36 nghìn, 84 nghìn | 82 nghìn, 166 nghìn |
| Vượt 45 s | 0 | 0 | 0 |

Số liệu từng câu: [summary.json](summary.json).

| ID | Baseline | A | B | Ghi chú |
|---|---:|---:|---:|---|
| BL-01 Lore Ranni | 19,3 s | 15,1 s | 15,7 s | |
| BL-02 Rivers of Blood | 7,9 s | 5,0 s | 12,3 s | B: lần viết đầu bị từ chối |
| BL-03 Mooonveil | 10,2 s | **3,3 s** | 8,6 s | A: `check_name` rồi `finish` ngay |
| BL-04 Godfrey | 16,1 s | 17,5 s | 12,7 s | |
| BL-05 Build Strength 125 | 36,6 s | 38,0 s | 18,8 s | Agent tự sửa calculator sau 2 lần lỗi, cả A và B |
| BL-06 Prisoner 30 + Moonveil | 36,1 s | 36,2 s | 27,2 s | Baseline calculator lỗi; spike đạt |
| BL-07 So sánh | 17,8 s | 12,0 s | 23,2 s | B: 3 lần viết bị từ chối |
| BL-08 Waterfowl Dance | 30,9 s | 11,0 s | 9,4 s | Spike không đi web; baseline có |
| BL-09 Quest Ranni | 11,1 s | 10,7 s | 16,1 s | |
| BL-10 SotE (EN) | 17,4 s | 6,6 s | 8,3 s | |

## Nhận xét

- **Ít lượt gọi model hơn hẳn**: A giảm từ 7,8 xuống 4,3 lượt/câu (−45%). Vòng lặp gộp Agent decision, Tool planner và Assessor; câu tra cứu thường chỉ cần 2–3 lượt Agent + 1 lượt viết.
- **Calculator tốt hơn**: cả hai biến thể đạt 2/2 (baseline 1/2). Agent đọc lỗi ("210/204 điểm", sàn class) và tự sửa số, không cần rule cân số phía server.
- **B nhanh ở câu build nhưng tốn token**: không có lượt Generator riêng nên câu build nhanh hơn (p95 25 s), nhưng token đầu vào gấp ~2,3 lần A vì ngữ cảnh dài dần qua từng bước; 6/10 câu có lần `final_answer` đầu bị `validate_answer` từ chối (trích dẫn/quote) và phải viết lại.
- **Câu build ở A vẫn chậm** (~37 s): 3 lần gọi calculator + lượt Generator. Ngữ cảnh lớn (~84 nghìn token) cũng làm mỗi lượt chậm.
- Không câu nào cần hỏi lại; prototype không dùng `search_web` lần nào (baseline dùng ở BL-08).

## Không so sánh được / hạn chế

- **Baseline đo qua API SSE và gồm bước chọn ảnh** (9 lượt `image_selection`); spike gọi thẳng prototype, **không chọn ảnh**, không lưu hội thoại. Độ trễ spike vì thế thấp hơn một phần không phải do kiến trúc.
- Baseline chưa ghi token, nên chưa so được chi phí.
- Một lượt chạy mỗi biến thể, 10 câu: so sánh thô, không có ý nghĩa thống kê. Độ trễ dao động theo mạng/provider.
- Chưa đo Discord, chưa đo câu có nhiều lượt hội thoại, chưa có memory/clarification thật (câu hỏi lại được gửi lại kèm lời đáp).
- Chất lượng câu trả lời mới đọc tay vài câu (đúng ngôn ngữ, có trích dẫn, bảng build đúng tổng), chưa chấm golden set.

## Đề xuất

Đi tiếp GĐ2 với **biến thể A** (Agent lặp gọi tool + Generator/Answer Guard riêng): ít lượt gọi và ít token nhất, giữ nguyên hợp đồng trích dẫn, stream và Answer Guard. Trước khi nối API cần: rút gọn kết quả tool đưa lại cho Agent (giảm token), giữ memory/clarification, chọn ảnh, và đo lại cùng bộ câu qua API. Biến thể B đáng xem lại khi ngữ cảnh đã gọn hơn.

## Chạy lại

Hướng dẫn, chưa tự chạy thêm: từ `D:\Index-Beastackend` (gọi API thật, tốn phí; cần PostgreSQL/Qdrant/Redis và `.env`):

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.spike_true_agent generator data/research_runs/spike-moi --manifest ../docs/testing/2026-11-22_spike-true-agent/manifest.json
```

Đổi `generator` thành `final_answer` cho biến thể B; thêm `--only BL-05,BL-06` để chạy vài câu. Script không ghi đè kết quả đã có. Kết quả thô lần này (câu trả lời, trace) ở `backend/data/research_runs/2026-11-22-spike/` (gitignored).
