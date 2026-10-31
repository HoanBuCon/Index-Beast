# Kiểm tra DeepSeek thật và sửa phục hồi protocol RAG

31/10/2026 · TV3 — MinhMuc · IndexBeast.
Nhánh `fix/s2-tv3-deepseek-live-output`. Không commit/push/merge; giữ mọi thay đổi cũ trong working tree.

## Nguyên nhân xác định được và phần chưa biết

Người dùng xác nhận câu gây lỗi request `43e14191-376e-4888-ad05-18b67f59b5b3` là
**“các boss trong elden ring”**. Stack lịch sử dừng ở nhánh LLMError/OutputFormatError, không có diagnostic reason.
Chưa tái hiện lại JSON lỗi của request đó, vì vậy không khẳng định nguyên nhân lịch sử là citation hoặc hết token.

Trong lượt kiểm tra thật đầu tiên với câu boss cuối và context mẫu, quan sát được một lỗi khác có bằng chứng:
model trả JSON hợp lệ, `insufficient=true`, evidence rỗng nhưng answer vẫn mô tả nguồn và chèn [1]/[2].
Validator chặn đúng bằng `insufficient_with_citations`. Code cũ chưa phục hồi loại protocol này;
format retry trước đó cũng dùng lại cùng thinking mode.

Hai lần dùng đúng câu người dùng qua hybrid retrieval thật trả answer có citation và vượt validation.
Đây là kiểm chứng một số lần chạy, không bảo đảm mọi câu hỏi hoặc mọi lần provider đều thành công.

## Năm completion thật đã thực hiện

Người dùng cho phép gọi DeepSeek. Ban đầu giới hạn 3 lượt, sau khi báo kết quả đã thông báo thêm tối đa 2 lượt;
tổng thực tế **5 completion**, không SDK transport retry. Không gọi thêm sau lượt thứ 5.
Script chẩn đoán tạm nằm trong .venv được ignore, có budget file chặn lượt thứ 6; không phải công cụ được commit.

| Lượt | Câu hỏi / phương pháp | Kết quả | Input / output token |
|---|---|---|---|
| [1](2026-10-31_live-output-1.json) | Boss cuối; context mẫu đọc trực tiếp artifact | JSON hợp lệ, bị chặn insufficient_with_citations | 2.978 / 187 |
| [2](2026-10-31_live-output-2.json) | Câu “các boss…”; 5 chunk Bosses mẫu | Thành công | 3.469 / 768 |
| [3](2026-10-31_live-output-3.json) | Đúng câu hỏi, cached E5 + hybrid Qdrant thật | Thành công | 3.154 / 517 |
| [4](2026-10-31_live-output-4.json) | Replay lỗi protocol tối giản, lượt phục hồi gọi DeepSeek thật | Thành công, recovery non-thinking, temperature 0 | 3.646 / 420 |
| [5](2026-10-31_live-output-5.json) | Đúng câu hỏi, cached E5 + hybrid Qdrant thật, sau sửa prompt/code | Thành công | 3.239 / 475 |

Tổng token provider báo: **16.486 input + 2.367 output = 18.853**; không ước tính tiền.
Lượt 4 có initial response mô phỏng rút gọn cùng pattern lỗi đã quan sát, không phải một completion trả phí thứ hai.
Chỉ nhánh recovery gọi provider ở lượt này; không gọi đây là hai lần API thật liên tiếp.

Các lượt đều history rỗng, rewrite tắt và SDK max_retries=0 trong settings bản sao.
Lượt 1/2/3/5 tắt format retry để mỗi lượt đúng một completion; lượt 4 cho đúng một recovery sau replay.
Không sửa .env thật hoặc khóa API. Hai lượt retrieval dùng cache local với HF_HUB_OFFLINE=1 và Qdrant đọc,
không tải model, upsert/index/create/drop collection. Các lượt 1/2/4 chỉ chọn context artifact local thủ công,
không được diễn giải là chất lượng retrieval hoặc replay history của request lịch sử.
Đây là kiểm tra prepare/retrieve/generate, chưa replay đầy đủ HTTP API/frontend hoặc image resolver.

Chỉ xem final content để chẩn đoán, không xem/lưu private reasoning. JSON report giữ metadata/usage counts
và answer hợp lệ khi có; không lưu raw output lỗi, prompt hoặc secret. Một số final content có literal escape
trong text; tác vụ này không thêm parser sửa facts/escape tùy tiện. Chất lượng trình bày/ngữ nghĩa vẫn cần review.

## Code đã sửa

- `RAGValidationError` mang mã lỗi static, vẫn kế thừa UpstreamError và giữ API code/status 502.
- Bổ sung recovery riêng cho `insufficient_with_citations` bằng cách **sinh answer mới**;
  không chấp nhận answer lỗi, không strip citation để né validator. Cùng ngân sách RAG_FORMAT_RETRIES 0/1 hiện có.
- Recovery JSON/rỗng/protocol dùng non-thinking và temperature 0, giữ nguyên question/history/evidence;
  lượt đầu giữ thinking cấu hình. Giữ JSON mode, không đổi model, không tăng token budget hoặc fallback llm_only.
- Prompt yêu cầu insufficient chỉ nêu thiếu gì/hỏi làm rõ, không mô tả nguồn/đưa facts/citation trong nhánh đó.
- SSE chỉ recovery trước khi gửi text; sau khi đã gửi vẫn error và không done khi validation thất bại.
- Diagnostic cuối dùng mức ERROR để reason vẫn hiện khi chỉ xem error log; thông báo phân biệt output rỗng,
  sai định dạng, bị ngắt và provider request failed. Không ghi raw output/reasoning.
- Adapter thêm http_status số hợp lệ, exception class trong allowlist; giữ các finish reason aborted và
  insufficient_system_resource theo [contract DeepSeek](https://api-docs.deepseek.com/api/create-chat-completion/).

Không bỏ kiểm tra quote/citation, không retry schema/quote sai hoặc mọi citation mismatch.
Output mới sai tiếp vẫn bị chặn. `grounded=true` chỉ là kiểm tra grounding hình thức, không chứng minh entailment.
Retrieval vẫn có thể lấy đoạn chưa sát (ví dụ Letter for Freyja ở đầu các lượt này), chưa có benchmark chất lượng mới.

## Kiểm thử offline và vận hành

Baseline gần nhất trước tác vụ: **467 passed, 1 warning**.
Kết thúc: **475 passed, 1 warning**, 19,74 giây; thêm regression cho lỗi thật/recovery, tắt retry,
SSE trước/sau token, wire thinking true→false và diagnostic provider đã lọc.
Không xóa assertion bảo vệ nguồn. Test wire cũ cập nhật để kiểm chủ đích mới: lượt đầu giữ cấu hình,
lượt recovery luôn non-thinking/temp 0, thay vì ép cả hai lượt cùng thinking.

Lệnh từ backend:

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest -c pyproject.toml tests/unit -q --tb=short
.venv/Scripts/python.exe -m ruff check app/adapters/llm.py app/rag/generator.py tests/unit/test_llm.py tests/unit/test_live_chat.py
.venv/Scripts/python.exe -m ruff format --check app/adapters/llm.py app/rag/generator.py tests/unit/test_llm.py tests/unit/test_live_chat.py
.venv/Scripts/python.exe -X utf8 -m scripts.export_openapi --check
```

Restart API nếu worker chưa reload: dừng ở terminal đang chạy rồi `make api` từ gốc.
Tạo chat mới để tránh ID history RAM hết hạn sau restart; hỏi lại “các boss trong elden ring”. Không cần reindex.
Nếu còn lỗi, dòng `Generation failed` mức ERROR sẽ có reason; gửi cùng request_id để phân biệt provider/format
với `RAG validation failed`. Không cần chia sẻ API key, prompt thô hoặc private reasoning.
