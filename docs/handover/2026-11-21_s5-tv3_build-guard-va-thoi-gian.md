# TV3 · Phân bổ chỉ số do Agent làm, Answer Guard, hạn thời gian và corpus Origins

Ngày 20–21/11/2026 · Nhánh `fix/s4-tv3-tach-han-thoi-gian` (base `origin/develop` tại `bcbbf4c`). Đã commit: `15c7d72`, `b09a2ac` (rule con số, có [handover riêng](2026-11-20_s4-tv3_agent-rule-con-so.md)) và `0d2f4df` (hạn thời gian). Phần còn lại đã commit và **merge vào `develop` qua PR #124** (`5a18e9c`). Việc tiếp theo: [handover 22/11](2026-11-22_s5-tv3_giu-cau-guard-va-agent-tu-quyet.md).

Liên quan: [bổ sung 11 trang Origins/Attributes vào corpus](2026-11-20_s5-tv2_bo-sung-trang-class.md) (việc TV2), [bỏ tùy chọn spoiler ở web/bot/API](2026-11-21_s5-tv4_bo-tuy-chon-spoiler.md) (việc TV4).

## Mục tiêu

Câu hỏi build phải ra một bảng phân bổ 8 chỉ số dùng được, nhanh, không bị chặn. Định hướng của TV3: phân bổ chỉ số chỉ là gợi ý tham khảo (không tính sát thương); Agent quyết định nội dung và cách trình bày; server chỉ giữ các ranh giới về nguồn.

## Thay đổi chính

### 1. Hạn thời gian (`0d2f4df`)

- `CHAT_STREAM_TIMEOUT_SECONDS=90`: hạn cả lượt SSE web (tính cả chờ token đầu). JSON/Discord giữ `CHAT_TIMEOUT_SECONDS=45`.
- `CHAT_PREPARE_TIMEOUT_SECONDS=25` (`Settings.prepare_budget_seconds`): ngân sách Agent + công cụ.
- Web `auto`: `CHAT_COVERAGE_STEPS=6`, `CHAT_COVERAGE_MAX_CALLS=12`; `CHAT_CALCULATOR_MAX_FAILURES=2`.
- Log `Chat deadline exceeded` ghi giai đoạn, node, thời gian từng bước, không ghi nội dung.

### 2. Calculator chỉ phân bổ điểm (`app/rag/build_data.py`, `tool_agent.py`)

- Tổng = level + 79 lấy từ snapshot có nguồn trong `knowledge/gameplay.json` (`rule_data.level_offset`); Agent thấy `build_rules` (tổng, trần) trước khi đề xuất.
- Chỉ số khởi đầu của class: Agent tự trích Infobox của trang class trong corpus (`build_data.starting_class`; mặc định Wretch khi người dùng không nêu). Server kiểm từng số gắn đúng chỉ số, trang đúng class, tổng khởi đầu = level của class + 79. Không trích thì sàn ghi "chưa kiểm".
- Yêu cầu vũ khí: tùy chọn, có nguồn thì kiểm; số gắn theo key chỉ số (hiểu "Int: 36", bảng cột "Required", viết tắt `Fth`).
- `fill`: Agent đặt vài chỉ số, calculator tính phần dư vào một chỉ số (cần đã trích Infobox class).
- Calculator bị rút sau 2 lần lỗi; gọi lại công cụ đã rút lần 2 thì dừng vòng lặp.
- JSON bước công cụ sai: ghi loại lỗi/tên trường, cho Agent sửa 1 lần; lần 2 mà có bằng chứng thì trả lời thay vì 502.
- Gói tri thức bỏ snapshot class (Wretch/Samurai); `scripts/prepare_gameplay_pack.py --rules-only` dựng lại phần quy tắc mà không cần chunk artifact.

### 3. Trình bày và guard (`app/rag/generator.py`, `prompts/{answer,tools,guard}.md`)

- Agent viết câu trả lời **tự in bảng Markdown** 8 chỉ số. Server chỉ thêm một dòng nêu giả định (class mặc định, vũ khí đề xuất, phần chưa kiểm) và trích nguồn quy tắc; nếu bảng thiếu, thêm dòng số đã kiểm.
- **Không hủy câu vì lỗi trình bày**: đoạn không trích dẫn được giữ (chỉ đếm `uncited_paragraphs`); evidence thừa bị bỏ; bảng sai số, thiếu bảng hoặc sai tổng thì gọi **Answer Guard** (một lượt LLM, `prompts/guard.md`) sửa. Câu build được giữ lại tới khi sửa xong mới hiện; câu khác vẫn stream. Guard làm hỏng trích dẫn thì giữ bản đầu; còn sai thì thêm bảng đã kiểm hoặc dòng lưu ý tổng.
- Chặn cứng còn lại: URL bịa, trích dẫn tới nguồn không có, quote không có trong nguồn, trích dẫn thiếu evidence, tên trường nội bộ (vẫn sinh lại; nên chuyển sang Guard).
- Payload generator có `build_check` (checked/failed/not_run) để câu trả lời nói đúng lý do khi không có bảng kiểm.

### 4. Bỏ tính năng tránh spoiler (phần backend)

Bỏ tham số và phép lọc spoiler ở corpus, Qdrant filter, retriever, pipeline, Tool Agent, ảnh, prompt và script. `spoiler_level` giữ làm metadata. Chi tiết và phần web/bot: handover TV4 ở trên.

## Kiểm tra

- Backend `pytest -q`: **1.149 passed, 20 skipped, 46 deselected** (36,7 s); Ruff check/format đạt; pre-commit đạt.
- Web: typecheck đạt, 71/71 test. Bot: typecheck đạt, 75/75 test.
- Test thật (web SSE, câu mới mỗi lần, kết quả ở `backend/data/research_runs/2026-11-2x-live-*`, gitignored):

| Lượt | Kết quả |
|---|---|
| live-3 (trước sửa) | Câu build 504 sau 45 giây |
| live-4 | Hết timeout; calculator lỗi nhãn cột |
| live-6 | Calculator chỉ phân bổ: 2/2 thành công |
| live-7 | Agent tự trích class: 0/2 (cộng sai tổng, 502 JSON) |
| live-8 | `fill` + sửa JSON: 2/2 thành công |
| live-9 | Agent tự in bảng nhưng bị guard chặn: 0/2 |
| live-10 | Guard mới: **2/2 đạt** (Warrior 115 Dex, Sword of Night and Flame 65), 24–25 giây, bảng do Agent in đúng số |

- **Chưa kiểm chứng**: Answer Guard chưa phải chạy lần nào khi chạy thật; độ trễ khi Guard sửa chưa đo; kênh Discord chưa đo.

## Hạn chế và việc còn lại

1. Kiểm chứng Answer Guard thật (câu dễ sai), đo độ trễ.
2. Prompt: không lặp số trong đoạn văn và bảng; nhập dòng giả định vào câu trả lời.
3. Chuyển `internal_field_name` sang Answer Guard.
4. Discord không hiển thị bảng Markdown: cần dạng danh sách theo kênh; đo câu build với hạn 45 giây.
5. Server vẫn làm hộ Agent: sửa chính tả tên (`entity_spelling.py`), fallback câu gốc, web search tự chạy theo assessor, `rank_fallback`, chặn `clarify` theo `reason`, bảng intent viết cứng, đoán ngôn ngữ, chọn đoạn web theo từ khóa. Dự kiến bỏ khi làm True Agent (decision của TV3 trong vault cá nhân, chưa có ADR trong repo).
6. Trần 99 chưa có nguồn (giới hạn hợp lệ trong code).
