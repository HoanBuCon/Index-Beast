# Phân tích và sửa lỗi output RAG không phải JSON

Ngày 31/10/2026 · IndexBeast · TV3 — MinhMuc.
Nhánh `fix/s2-tv3-rag-json-output`, nền develop `35cce86` (sau PR #47).

## Điều xác định được

Request `b54ef9d5-00f7-4657-85bb-0e91f611c720` có DeepSeek HTTP 200, `finish_reason=stop`,
nhưng `json.loads(result.content)` trong generator ném JSONDecodeError. Backend chuyển thành 502.
Đây là lỗi **định dạng nội dung generation**, không phải lỗi kết nối DeepSeek, Qdrant hoặc đọc dataset
trong stack trace được cung cấp. `stop` không xác nhận JSON đúng hoặc answer có evidence.

Đã đọc pipeline, adapter, prompt, service, phiên bản SDK cài trong môi trường và test request wire:

- Khi không chọn được context, pipeline dùng static answer, bỏ qua generation. Điều này giải thích vì sao
  người dùng thấy nhánh "không có dữ liệu" không gặp lỗi parse.
- Có context nhưng chưa đủ bằng chứng khác với không có context: vẫn gọi generation, yêu cầu
  `insufficient=true`, `evidence=[]`, không citation. Đây là một kết quả hợp lệ, không phải lỗi hệ thống.
- Code có gửi `response_format={"type":"json_object"}`; test qua ChatDeepSeek/SDK thật với HTTP giả
  xác nhận tham số không bị rơi trong LCEL, ở cả thinking và non-thinking. Role/history giữ nguyên.
- Điểm yếu code cũ: chỉ parse trực tiếp rồi thất bại ngay khi output có lỗi cú pháp/lớp bọc;
  prompt được siết ở PR #47 nhưng chưa có cơ chế phục hồi định dạng.

Không có output thô của request trên, do đó **chưa xác định được ký tự lỗi cụ thể**, có code fence hay không,
hoặc nguyên nhân khiến provider sinh sai. Không gán lỗi này cho thiếu dataset, Unicode người dùng,
hết token hoặc thinking khi chưa có bằng chứng. Hai lượt live ở báo cáo trước không bảo đảm độ ổn định.

[Tài liệu JSON Output chính thức](https://api-docs.deepseek.com/guides/json_mode/) yêu cầu JSON mode,
chỉ dẫn JSON kèm ví dụ và budget phù hợp; cũng nêu khả năng content toàn khoảng trắng dù finish=stop.
Đó là lý do cần xử lý output lỗi/rỗng; không chứng minh request này là trường hợp toàn khoảng trắng.
[Tài liệu thinking](https://api-docs.deepseek.com/guides/thinking_mode/) nêu temperature không có tác dụng
khi bật thinking. Không thay temperature hoặc chuyển chế độ để che lỗi.

## Đã sửa

1. **Prompt:** yêu cầu JSON kể cả từ chối/thiếu evidence; escape newline/quote; nhắc rằng history dạng text
   không phải mẫu định dạng cho lượt hiện tại. Không thêm instruction từ nguồn vào policy.
2. **Parser dùng chung:** nhận toàn bộ JSON, cho phép bỏ duy nhất BOM/code fence bao trọn JSON hoàn chỉnh.
   Không trích object con, sửa trailing comma, thêm dấu đóng hoặc sửa facts. Chặn duplicate key,
   NaN/Infinity, JSON quá lớn/quá sâu và trailing prose; vẫn chạy schema/citation/quote validation sau parse.
   Đây là khả năng phòng vệ, không phải khẳng định code fence là nguyên nhân request lịch sử.
3. **Recovery có giới hạn:** `RAG_FORMAT_RETRIES` nhận 0 hoặc 1, mặc định 1. Chỉ retry output JSON lỗi/rỗng,
   cùng question/history/context, không đưa output lỗi hoặc reasoning vào prompt. Không retry grounding,
   schema, network, finish=length, payload quá lớn/quá sâu. Không fallback llm_only.
4. **Streaming:** cùng decoder, giữ streaming thật và cleanup/cancellation. Chỉ retry trước token đáp án đầu tiên.
   Đã gửi text rồi thì phát error, không tự thay answer hoặc phát done thành công. Không lưu answer thất bại.
5. **Diagnostic:** vị trí JSON dòng/cột/offset, độ dài, mã lỗi cố định và loại wrapper; không ghi raw output,
   provider-controlled error text hoặc reasoning. Usage JSON cộng token các attempt được provider báo,
   gồm completion sai bị bỏ. Stream chưa thu thập usage token cho retry.

Một request lỗi format có thể tốn thêm một lượt generation và thời gian chờ. `LLM_MAX_RETRIES` của SDK
là retry transport riêng; giới hạn format không đồng nghĩa giới hạn tuyệt đối số lần HTTP khi có lỗi mạng.
Không sửa `.env` thật; default hoạt động khi biến mới chưa khai báo. `.env.example` và Compose đã đồng bộ.

## Kiểm thử thực tế — không API/model/server thật

Baseline từ `backend/`: **377 passed, 1 warning**, 16,66 giây.
Sau sửa: **429 passed, 1 warning**, 17,09 giây; thêm **52 case**. Warning Qdrant memory về payload index là dự kiến.

Các case mới bao gồm:

- VI/EN: không context không gọi model; context thiếu evidence trả insufficient hợp lệ, không retry.
- HTTP giả chạy qua LangChain/SDK thật: thinking/non-thinking đều gửi JSON mode, không tool calling,
  cùng history/evidence khi retry, không gửi output lỗi vào prompt.
- API JSON phục hồi sau một lỗi, hết số lần thì 502, không ghi answer lỗi vào history/trace message.
- Không retry lỗi transport, length, schema, citation/quote; wrapper không vượt qua grounding checks.
- JSON nguyên vẹn, BOM/fence, Unicode/escape chia token, duplicate key, NaN, trailing prose,
  nhiều object, thiếu dấu đóng, quá lớn/quá sâu; không sửa/cắt JSON để đạt validation.
- SSE trước/sau token đầu tiên, cleanup từng attempt, nguồn và text nhất quán, không done khi thất bại.
- Config 0/1 và giới hạn; usage completion bị bỏ vẫn được tính khi đã có số token.

Lệnh đã chạy từ `backend/`:

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest -c pyproject.toml tests/unit -q --tb=short
.venv/Scripts/python.exe -m ruff check app/rag/generator.py app/rag/output.py app/rag/pipeline.py core/config.py tests/unit/test_config.py tests/unit/test_live_chat.py tests/unit/test_llm.py tests/unit/test_rag_output.py
.venv/Scripts/python.exe -m ruff format --check app/rag/generator.py app/rag/output.py app/rag/pipeline.py core/config.py tests/unit/test_config.py tests/unit/test_live_chat.py tests/unit/test_llm.py tests/unit/test_rag_output.py
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -X utf8 -m scripts.export_openapi --check
```

Ruff/format, pip check và OpenAPI check đạt. Không collect integration suite hoặc route test_llm ngoài unit.
Không gọi thêm DeepSeek thật, tải/chạy embedding, index, ghi DB/Qdrant hoặc thay dữ liệu gốc.
HTTP fake không chứng minh provider sẽ trả đúng ở lượt thử tiếp theo; provider liên tục trả sai vẫn bị chặn.
Chưa chạy lại UI/Discord hoặc đo tỉ lệ phục hồi trên tập câu hỏi thật.

## Người dùng tự thử sau sửa — chưa thực thi thay

Restart tiến trình API bằng `make api` từ gốc nếu chưa reload. Không cần index lại.
Thử lại câu hỏi và một câu thiếu bằng chứng; generation thật có dùng số dư API.
Muốn tắt lượt bổ sung, tự đặt `RAG_FORMAT_RETRIES=0` trong `.env` rồi restart API.

Nếu vẫn lỗi, gửi request_id cùng log `Retrying RAG generation`, `Generation failed`,
`RAG validation failed` hoặc `Citation index mismatch`. Mã `json_error=syntax` có dòng/cột;
không cần gửi key, prompt hoặc private reasoning. Không chuyển lỗi JSON thành câu trả lời "không có dữ liệu".
