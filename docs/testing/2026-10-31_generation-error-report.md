# Chẩn đoán lỗi trả lời câu hỏi boss cuối

Ngày 31/10/2026 · IndexBeast · TV3 — MinhMuc.

## Kết luận và giới hạn

HTTP 200 từ DeepSeek chỉ xác nhận request provider thành công. Backend vẫn có thể trả 502
nếu output thiếu, JSON lỗi hoặc citation/evidence không hợp lệ.
Log cũ của request `29c26b07-498f-4aee-89b2-cd0cb5d01245` gom lỗi qua `UpstreamError`,
chưa đủ thông tin để xác định chính xác nguyên nhân lịch sử.

Đã dùng **đúng 2 lượt completion thật** được người dùng cho phép, với câu hỏi
`boss cuối của game là con gì?`. Lượt đầu tái hiện lỗi `citation_evidence_indices`;
lượt sau khi bổ sung hướng dẫn protocol trả lời thành công, có nguồn.
Trong lượt đầu, `finish_reason=stop`, JSON parse được, output 240 token;
không có bằng chứng hết ngân sách token trong lượt này.
Không lưu answer/evidence thô của lượt lỗi nên không xác định được cặp chỉ số sai cụ thể.

## Cách chạy thực tế

- Chạy pipeline prepare/generate thật, query embedding E5 đã cache, đọc Qdrant và gọi DeepSeek.
- Model `deepseek-flash`, thinking bật, budget 4.096 token, temperature 0,2;
  không sửa `.env`, không tăng budget. Mỗi lượt tắt retry (`max_retries=0`) và rewrite.
- History rỗng vì không có history của request lỗi ban đầu. Context tối đa 5 nguồn.
- Hai lần chạy bằng script chẩn đoán tạm trong môi trường local; không phải replay toàn bộ HTTP API,
  không chạy bước chọn ảnh hoặc frontend. Script tạm không thuộc bộ công cụ được bàn giao.
- Không index/upsert dữ liệu, không tạo lại collection. Không ghi nội dung private reasoning,
  key hoặc response lỗi thô vào báo cáo.

| Lượt | Kết quả | Finish | Token vào / ra | Citation |
|---|---|---|---|---|
| [1 — trước sửa prompt](2026-10-31_generation-repro-1.json) | Bị validator từ chối | stop | 2.981 / 240 | Tập citation và evidence không khớp |
| [2 — sau sửa prompt](2026-10-31_generation-repro-2.json) | Thành công, grounded=true | stop | 3.114 / 159 | Answer/evidence cùng [1, 5] |

Câu trả lời lượt 2 xác định boss cuối bản gốc là **Elden Beast**, dẫn nguồn [1] và [5].
Thứ tự retrieval giữa hai lượt khác nhau: Elden Beast ở vị trí 2 rồi vị trí 1.
Vì vậy đây là một lần kiểm chứng thành công sau sửa, chưa phải thí nghiệm chứng minh quan hệ nhân quả
hoặc bảo đảm mọi lần sinh sau này đều đúng. `grounded=true` phản ánh validation citation/quote,
không phải chứng minh entailment ngữ nghĩa.

## Thay đổi

- [Adapter LLM](../../backend/app/adapters/llm.py): diagnostic có reason, finish reason và token counters
  hợp lệ khi có; chỉ cho phép mã biết trước, không đưa response/reasoning vào diagnostic.
- [Generator](../../backend/app/rag/generator.py): log `Generation failed` có reason an toàn;
  log `Citation index mismatch` chỉ chứa các chỉ số; giữ nguyên từ chối output không hợp lệ.
- [Prompt](../../backend/app/rag/prompts/answer.md): giữ chỉ số nguồn server, không đánh lại số;
  mỗi citation có đúng evidence tương ứng, không thêm evidence thừa; câu hỏi làm rõ có protocol riêng.
- Unit test thêm 9 case, gồm nguồn ở vị trí 2, citation mismatch vẫn bị chặn, output thiếu/JSON lỗi,
  diagnostic không lộ nội dung và SSE lỗi không phát `done` thành công.

Không thêm automatic retry/repair hoặc bỏ validation để che lỗi.

## Kiểm tra đã chạy

Từ `backend/`:

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest -c pyproject.toml tests/unit/test_llm.py tests/unit/test_live_chat.py -q --tb=short
.venv/Scripts/python.exe -X utf8 -m pytest -c pyproject.toml tests/unit -q --tb=short
.venv/Scripts/python.exe -m ruff check app/adapters/llm.py app/rag/generator.py tests/unit/test_llm.py tests/unit/test_live_chat.py
.venv/Scripts/python.exe -m ruff format --check app/adapters/llm.py app/rag/generator.py tests/unit/test_llm.py tests/unit/test_live_chat.py
.venv/Scripts/python.exe -X utf8 -m scripts.export_openapi --check
```

Nhóm test liên quan: **107 passed**. Toàn bộ unit: **377 passed, 1 warning**, 16,13 giây.
Warning Qdrant local không thực thi payload index là hạn chế của memory test.
Ruff check/format và OpenAPI check đạt; không thay API schema hoặc dependencies.
Không đo benchmark chất lượng mới, không chạy integration suite hay Discord thật.

## Hướng dẫn thử tiếp — chưa chạy thay người dùng

Nếu API chưa tự reload, dừng tiến trình API ở terminal đang chạy rồi dùng `make api` từ gốc project.
Hỏi lại câu trên trên web. Request mới có thể dùng số dư API; hai lượt cho phép của tác vụ này đã hết.
Nếu còn lỗi, lấy request_id và các dòng `Generation failed`, `Citation index mismatch`,
`RAG validation failed`; không cần chia sẻ key, prompt thô hoặc private reasoning.

Không cần embedding/index lại để áp dụng thay đổi này. Lỗi protocol từ model vẫn có thể xảy ra;
backend tiếp tục trả lỗi thay vì công bố answer không vượt validation.
