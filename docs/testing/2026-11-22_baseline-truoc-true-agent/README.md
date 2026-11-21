# Baseline trước True Agent — 22/11/2026

TV3 MinhMuc · Nhánh `fix/s5-tv3-guard-giu-cau-va-prompt-build` (chưa commit, base `develop` `5a18e9c`). Mục đích: số liệu để so sánh khi thay pipeline nhiều vai (Agent decision → Tool planner → Assessor → Generator → Answer Guard) bằng một vòng lặp True Agent.

## Cách chạy

- 10 câu cố định ([manifest.json](manifest.json)), mỗi câu một lượt mới, web SSE `/api/v1/chat/stream` qua ASGI app thật (`.env` thật, PostgreSQL/Qdrant/Redis local, DeepSeek, Jina reranker, Tavily), `web_search=auto`, `lang=auto`.
- Một lượt chạy duy nhất (không lặp lại để lấy trung bình), nên độ trễ có dao động mạng/provider.
- Lượt bổ sung chỉ gửi khi Agent hỏi lại; lần này không câu nào hỏi lại.
- Số liệu tổng hợp: [summary.json](summary.json). Kết quả thô (câu trả lời, trace) nằm ở `backend/data/research_runs/2026-11-22-baseline/` (gitignored).
- Độ trễ đo phía client, gồm cả việc giữ câu tới khi kiểm xong (chữ đầu tiên đến cùng lúc với cả câu).

## Kết quả tổng

| Chỉ số | Giá trị |
|---|---|
| Trả lời được (HTTP 200, `done`) | **10/10** |
| Grounded (có trích dẫn hợp lệ) | **10/10** |
| Độ trễ p50 / p95 / max | **17,6 s / 36,4 s / 36,6 s** (trung bình 20,3 s) |
| Câu vượt 45 s (hạn JSON/Discord) | 0 |
| Lượt gọi model mỗi câu | trung bình **7,8**, tối đa 11 |
| Bước công cụ mỗi câu | trung bình **3,7**, tối đa 6 |
| Bước công cụ bị từ chối | 2 (JSON bước công cụ sai trường) |
| Calculator (2 câu build) | 1 checked, 1 failed |
| Answer Guard chạy | 0 lần |
| Chọn bằng chứng | Agent chọn ở 10/10 câu (không câu nào phải dùng `all_evidence`) |

## Từng câu

| ID | Loại | Thời gian | Lượt model | Bước công cụ | Ghi chú |
|---|---|---:|---:|---:|---|
| BL-01 | Lore (Ranni) | 19,3 s | 7 | 3 | |
| BL-02 | Tìm đồ (Rivers of Blood) | 7,9 s | 6 | 2 | Nhanh nhất |
| BL-03 | Tên gõ sai (Mooonveil) | 10,2 s | 8 | 3 | Agent tự chọn "Moonveil" từ ứng viên; 1 lượt sửa decision |
| BL-04 | Tên mơ hồ (Godfrey) | 16,1 s | 7 | 3 | Agent tự hiểu đúng boss, không hỏi lại |
| BL-05 | Build Strength level 125 | 36,6 s | 9 | 6 | Calculator lỗi lần 1 (210/204 điểm), **Agent tự sửa, lần 2 đạt** |
| BL-06 | Prisoner 30 + Moonveil | 36,1 s | 10 | 6 | Calculator lỗi 2 lần (lần 1 thiếu điểm cho sàn Strength, lần 2 sai kiểu `starting_class.level`) → bảng tham khảo tự tính |
| BL-07 | So sánh Uchigatana / RoB | 17,8 s | 11 | 6 | Chạm `step_budget`; coverage partial 2 lần, Agent không chọn tìm web |
| BL-08 | Né Waterfowl Dance | 30,9 s | 8 | 4 | Có web search |
| BL-09 | Quest Ranni | 11,1 s | 6 | 2 | |
| BL-10 | Khu vực SotE (tiếng Anh) | 17,4 s | 6 | 2 | |

Phân bổ lượt gọi model (10 câu, 78 lượt): `tool_decision` 37, `decision` 10 (+1 `decision_repair`), `assessment` 11, `generation` 10, `image_selection` 9.

## Nhận xét

- Câu build là phần chậm và tốn nhất (36 s, 6 bước công cụ, 9–10 lượt gọi); các câu tra cứu thường 8–20 s.
- **Gần một nửa lượt gọi model là `tool_decision`** (37/78): mỗi bước công cụ là một lượt gọi riêng. Đây là chỗ True Agent (function calling, gộp decision/planner/assessor) có thể giảm.
- Calculator: Agent đã tự sửa được một lỗi cộng điểm (BL-05) khi đọc thông báo lỗi; lỗi còn lại là sai kiểu dữ liệu trong `build_data` (BL-06). Đúng hướng "Agent tự sửa từ lỗi" của True Agent, nhưng chưa ổn định.
- Answer Guard không phải chạy lần nào: chưa có số liệu về độ trễ khi Guard sửa.
- Không câu nào cần hỏi lại; câu so sánh (BL-07) dừng ở trần bước khi bằng chứng còn thiếu.

## Hạn chế

- 10 câu, một lượt: đủ để so sánh thô (cùng bộ câu, cùng cách đo), không đủ để kết luận thống kê.
- Chưa đo kênh Discord/JSON (hạn 45 s) và chưa đo token/chi phí từng câu.
- Đánh giá chất lượng câu trả lời mới ở mức đọc tay vài câu, chưa chấm theo golden set.

## Chạy lại để so sánh

Từ `D:\Index-Beast\backend`, sau khi bật PostgreSQL/Qdrant/Redis và có `.env` (gọi API thật, tốn phí): sao chép thư mục `backend/data/research_runs/2026-11-22-baseline/` thành thư mục mới (runner từ chối chạy khi đã có `results.json`), xóa `results.json`/`run.log`, rồi chạy `.venv/Scripts/python.exe -X utf8 <thư mục mới>/run_live.py`. Dùng cùng [manifest.json](manifest.json) để so sánh.
