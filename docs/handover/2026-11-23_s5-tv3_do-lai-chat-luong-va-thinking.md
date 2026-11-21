# TV3 · Đo lại chất lượng sau `run_python`, sửa ngân sách Agent, tối ưu bước viết, thinking có chọn lọc

Ngày 23/11/2026 · Nhánh `feature/s5-tv3-do-lai-chat-luong` (từ `develop` sau PR #129). **Chưa commit**; chưa push, chưa có PR. Báo cáo đo: [docs/testing/2026-11-23_do-lai-sau-run-python/](../testing/2026-11-23_do-lai-sau-run-python/README.md). Quyết định nền: [ADR 006](../adr/006-true-agent.md).

## Phạm vi

1. Đo lại chất lượng sau PR #129 (`run_python` thay calculator, thay 5 rule cứng): 10 câu baseline, 4 câu build, 6 câu nhắm rule mới và Answer Guard (báo cáo mục 1–4).
2. Sửa gói A–E (MinhMuc duyệt): ngân sách Agent, lượt `finish` bắt buộc, prompt build, lỗi `set_conditions`, thử lại index trích dẫn (mục 5).
3. Tối ưu bước viết: đo, chọn ảnh song song, câu trả lời gọn (mục 6).
4. Thinking có chọn lọc: bước viết chỉ nghĩ khi Agent yêu cầu; thử thinking cho Agent (mục 7).

## Thay đổi

| File | Nội dung |
|---|---|
| `backend/app/rag/true_agent.py` | Ngân sách đếm lượt gọi model (input có `model_calls`, nhắc khi còn ≤ 3); hết lượt/hết giờ thì lượt cuối chỉ có `finish` (`tool_choice="finish"`, trace `agent.forced_finish`); lỗi `set_conditions` tách hai thông báo; `evidence_ids` tối đa 5; `finish.needs_reasoning`; cờ `CHAT_AGENT_THINKING`; cộng `reasoning_tokens` của Agent; trace bước có `error`/`fields` |
| `backend/app/rag/generator.py` | Trace `writer[]` mỗi lần sinh (`first_chunk_ms`, `generation_ms`, `output_chars`, token, `reasoning_tokens`), ghi usage cả đường stream; `Prepared.reasoning`; thinking = cấu hình cho phép **và** Agent yêu cầu, lần sinh lại luôn tắt; trace `writer_thinking`; `unknown_evidence_index` được sinh lại một lần |
| `backend/app/services/chat.py` | Chọn ảnh ngay khi Agent `finish`, song song với bước viết; sau khi viết chỉ giữ ảnh của nguồn được trích dẫn, không còn ảnh thì chọn lại một lần (`images.parallel = "fallback"`); `images.ms` |
| `backend/app/adapters/llm.py` | `ManagedChatDeepSeek._get_request_payload` gửi lại `reasoning_content` của tin nhắn assistant (DeepSeek bắt buộc khi thinking + tool, thiếu thì 400; `langchain_deepseek` 1.1.1 không tự làm) |
| `backend/app/rag/prompts/true_agent.md` | Ngân sách lượt gọi; build chỉ mở trang class và vũ khí, code tự chia phần dư và `assert` một lần; chép đúng lời người chơi; khi nào đặt `needs_reasoning` |
| `backend/app/rag/prompts/answer.md` | Độ dài mục tiêu theo loại câu, không lặp, bảng build 2 cột |
| `backend/core/config.py`, `.env.example` | `CHAT_AGENT_THINKING=false`; chú thích mới cho `RAG_THINKING_ENABLED` |
| `backend/scripts/run_live_manifest.py` | Cờ chẩn đoán `--capture-python`, `--capture-agent`; ghi thêm `writer`, `writer_thinking`, `agent.needs_reasoning`, `agent.thinking` |
| `backend/app/rag/README.md`, `docs/adr/006-true-agent.md` | Cập nhật mô tả thinking, ngân sách |
| Test | `test_true_agent.py`, `test_live_chat.py`, `test_llm.py`, `test_answer_media.py`, `test_agent_durable.py`, `test_evidence_guards.py` |

## Quyết định và quy ước

- **Thinking**: `RAG_THINKING_ENABLED` giờ là công tắc *cho phép*. `true`: bước viết chỉ nghĩ ở câu Agent khai báo `needs_reasoning=true` (nguồn mâu thuẫn hoặc phụ thuộc điều kiện, so sánh nhiều tiêu chí, quest/route nhiều bước). `false`: không bao giờ nghĩ. Server không đặt rule theo intent. Answer Guard, lần sinh lại, chọn ảnh, rewrite ảnh luôn tắt.
- `CHAT_AGENT_THINKING` chỉ để thử, mặc định tắt; MinhMuc đã chốt giữ tắt sau khi xem số đo. Đo cho thấy chậm hơn, gây lượt `finish` bắt buộc vì chạm hạn, không tăng grounded. Nếu bật thì nên tăng `CHAT_AGENT_TIMEOUT_SECONDS` (12 s không đủ).
- Ngân sách Agent đếm lượt gọi model, không đếm số tool trong một lượt.

## Trace đổi khóa (báo TV1)

- Bỏ: `tool_actions`, `checked_build`.
- Thêm: `agent.steps[].error`, `agent.forced_finish`, `agent.needs_reasoning`, `agent.thinking`, `agent.usage.reasoning_tokens`, `writer[]`, `writer_thinking`, `evidence_merged`, `images.ms`, `images.parallel`.
- Gỡ setting: `GAMEPLAY_KNOWLEDGE_ENABLED`, `WEB_SEARCH_ASSESSMENT_SECONDS`.

## Kiểm tra đã chạy

- Unit: `pytest tests/unit` **944 passed**, 20 skipped; ruff check/format và pre-commit trên các file đổi đạt.
- Chạy thật qua ASGI app (`.env` dev, DeepSeek/Tavily/Jina thật), số liệu trong báo cáo. Kết quả thinking (mục 7): (a) bước viết theo Agent: 14/14 + 6/6 grounded, 14 câu mới trung bình 13,7 s (bật mọi câu: 17,4 s; tắt hẳn: 12,1 s), đoạn không trích dẫn 16 (bật mọi câu: 12; tắt hẳn: 19), 6 câu khó trung bình 19,9 s, 0 đoạn không trích dẫn. (b) thêm Agent thinking: cũng grounded hết, nhưng 19,8 s và 33,6 s, 3 lượt `finish` bắt buộc, HR-02 45,2 s; không có lỗi 400.

## Cách dùng

- Cấu hình đề xuất: `RAG_THINKING_ENABLED=true`, `CHAT_AGENT_THINKING=false`. `.env` dev hiện đã là `true`, không cần đổi.
- Đo lại một manifest (gọi API thật, tốn phí), từ `backend/`:
  `.venv/Scripts/python.exe -X utf8 -m scripts.run_live_manifest ../docs/testing/2026-11-23_do-lai-sau-run-python/manifest-cau-kho.json data/research_runs/<thư-mục-mới>`

## Hạn chế và việc còn lại

- Câu build không nghĩ còn 2–3 đoạn không trích dẫn mỗi câu; nếu cần thì xử lý bằng prompt, không bật thinking.
- Agent đôi khi xin nghĩ khi không cần (NB-03 tìm vị trí vật phẩm).
- Meta-prompt có dự định ghi lý do Agent xin nghĩ; chưa thêm trường lý do, trace chỉ có cờ.
- Đường `reply` vẫn lộ tên trường nội bộ (AG-2). NB-04 (câu chiến thuật boss) có lúc tìm rất nhiều.
- `tool_choice` ép một hàm khi thinking bật chưa có trong tài liệu DeepSeek, nên lượt `finish` bắt buộc luôn tắt thinking.
- Docs còn sót: `agent-semantic-memory.md` (cờ cũ), mô tả chọn ảnh song song trong `docs/api/evidence-media-build.md`.
