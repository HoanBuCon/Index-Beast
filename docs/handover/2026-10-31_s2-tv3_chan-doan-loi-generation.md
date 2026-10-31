# Bàn giao chẩn đoán lỗi generation và citation

Ngày 31/10/2026 · TV3 — MinhMuc · nhóm 4 Hollows.
Nhánh `fix/s2-tv3-generation-diagnostics`, từ develop tại `437e30f`.
Chưa commit/push, chưa tạo PR hoặc merge. Không thay `.env`, dữ liệu nguồn, index hoặc frontend.

## Phạm vi và sự cố

Người dùng gặp 502 sau DeepSeek HTTP 200 với câu `boss cuối của game là con gì?`.
Log lịch sử chưa đủ xác định lỗi output cụ thể. Người dùng cho phép tối đa 2 completion thật;
đã dùng hết 2 lượt, mỗi lượt không retry, không gọi thêm nếu chưa có yêu cầu mới.

[Báo cáo kiểm tra](../testing/2026-10-31_generation-error-report.md) ghi phương pháp và giới hạn.
[Lượt 1](../testing/2026-10-31_generation-repro-1.json) lỗi citation/evidence mismatch dù finish=stop,
JSON parse được. [Lượt 2](../testing/2026-10-31_generation-repro-2.json) trả lời Elden Beast,
nguồn [1, 5], vượt validation. Thứ tự context thay đổi giữa hai lượt; không coi đây là chứng minh
prompt giải quyết mọi trường hợp. Không suy ra nguyên nhân lịch sử chắc chắn từ một lần tái hiện.

## File và quy tắc

- [llm.py](../../backend/app/adapters/llm.py): `LLMError.diagnostics` dùng mã reason/finish cho phép,
  chỉ thêm token counters là số nguyên không âm; không log message/body/reasoning của provider.
- [generator.py](../../backend/app/rag/generator.py): ghi nguyên nhân an toàn cho generation lỗi;
  citation mismatch ghi hai tập số. Giữ validator và fail-closed, không tự sửa citation.
- [answer.md](../../backend/app/rag/prompts/answer.md): không đánh lại số nguồn; citation và evidence
  phải tương ứng, kể cả nguồn được trích đầu tiên có index khác 1.
- [test_llm.py](../../backend/tests/unit/test_llm.py),
  [test_live_chat.py](../../backend/tests/unit/test_live_chat.py): thêm 9 case regression,
  giữ kiểm tra SSE lỗi không phát done và không rò rỉ nội dung trong diagnostic.
- Hai JSON repro và báo cáo testing lưu thống kê/final answer hợp lệ, không lưu reasoning hoặc secret.

Không tăng max_tokens, đổi thinking, bỏ assertion, thêm retry hoặc sửa logic retrieval/image.
Citation/quote validation chỉ kiểm grounding hình thức, không được gọi là chứng minh entailment.

## Kiểm tra thực tế

- Nhóm unit LLM/live chat: **107 passed**.
- Toàn bộ `tests/unit` theo `pyproject.toml`: **377 passed, 1 warning**, 16,13 giây.
- Ruff check/format trên 4 file Python sửa và OpenAPI `--check`: đạt.
- Warning Qdrant memory về payload index vẫn là hạn chế dự kiến, không phải server test.
- Hai lượt live dùng history rỗng, prepare/retrieve/generate thật; không replay HTTP API đầy đủ,
  không kiểm lại frontend, persistence hoặc image resolver trong lượt này.

Lệnh kiểm thử và kết quả chi tiết nằm trong báo cáo testing. Không gọi thêm model để thử ngẫu nhiên.

## Cách dùng và phần còn lại

Restart API bằng `make api` từ gốc nếu worker chưa reload, rồi người dùng tự thử trên web.
Không cần reindex. Khi lỗi, tìm theo request_id:
`Generation failed` (reason/finish/token nếu có), `Citation index mismatch` (chỉ số),
`RAG validation failed` (mã lỗi validation).

Nếu vẫn lặp lại, thu thập diagnostic an toàn trước khi quyết định thử model hoặc chiến lược retry mới.
Không hạ validation để đạt demo; câu trả lời không đúng protocol tiếp tục bị chặn.
Chưa chứng minh chất lượng ngữ nghĩa trên toàn golden set hoặc độ ổn định dài hạn của provider.
Nhóm review diff và tạo PR về develop khi có yêu cầu; không tự merge.
