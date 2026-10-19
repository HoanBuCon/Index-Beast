# Bàn giao DeepSeek LLM

Ngày: 19/10/2026. Phụ trách: TV3 (MinhMuc). Nhánh: `feature/s1-tv3-deepseek-api`.

Adapter dùng **API key từ DeepSeek Platform**, đọc `.env` ở gốc repository qua `Settings` dùng chung.
Model mặc định là `deepseek-flash`, thinking tắt. Việc nạp tiền và key dùng trên DeepSeek Platform phục vụ API này.

## Cấu hình và chạy thử

Giữ key thật trong `.env`, không chép vào mã nguồn hoặc commit. Các biến có sẵn trong `.env.example`:

```dotenv
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=2048
LLM_TIMEOUT_SECONDS=60
LLM_MAX_RETRIES=2
```

Thứ tự ưu tiên: biến môi trường thật > `.env` > mặc định. API key dùng `SecretStr` để tránh lộ khi in `Settings`.
Giới hạn output của adapter là 1–8192 token/lượt, timeout mặc định 60 giây cho SDK và tối đa 2 lần retry.
SDK có thể retry lỗi kết nối, 408/409/429/5xx. Đây không phải deadline cứng cho cả chuỗi retry.

Trong PowerShell, từ `D:\Index-Beast`:

```powershell
cd backend
.\.venv\Scripts\python.exe -X utf8 -m scripts.llm_smoke
.\.venv\Scripts\python.exe -X utf8 -m scripts.llm_smoke --json
.\.venv\Scripts\python.exe -X utf8 -m scripts.llm_smoke --stream
```

Mỗi lệnh trên **gọi API thật và tiêu hao credits**, giới hạn output 128 token. Không cần khởi động PostgreSQL,
Redis hoặc Qdrant để chạy các lệnh này. Đây là kiểm tra kết nối LLM, chưa phải kiểm tra chất lượng RAG.

Adapter không dùng thêm thư viện ngoài các dependency đã có trong `requirements.txt` và `constraints.txt`.
Để cài đúng môi trường Python trên Windows, dùng tùy chọn `-X utf8` khi cài các file requirements có chú thích tiếng Việt.

## Dùng trong backend

```python
from app.adapters.llm import DeepSeekLLM

async def example():
    async with DeepSeekLLM() as llm:
        result = await llm.complete([
            {"role": "system", "content": "Answer only using the supplied context."},
            {"role": "user", "content": "Context: ...\nQuestion: ..."},
        ])
        print(result.content)
        print(result.prompt_tokens, result.completion_tokens)
```

- `complete(messages)` trả `LLMResponse`: content, model, prompt_tokens, completion_tokens, finish_reason,
  reasoning_content và reasoning_tokens (hai trường sau có thể là `None` khi provider không cung cấp).
- `complete(..., thinking=True, reasoning_effort="low")` bật thinking, effort hỗ trợ `low`, `high`, `max`.
  Khi bật thinking, adapter không gửi temperature vì DeepSeek không hỗ trợ tham số đó trong chế độ này.
- `complete_json(messages)` bật JSON output, thêm chỉ dẫn JSON, parse và yêu cầu kết quả là object. Service gọi phải
  kiểm tra tiếp schema của tác vụ, ví dụ `query_en`, `lang`, `entities`. Chưa tự viết lại truy vấn.
- `stream(messages)` trả async iterator chứa các đoạn text của câu trả lời, không phát reasoning.
- Có thể truyền `max_tokens` và `temperature` cho từng lời gọi.
- Lỗi SDK/HTTP được chuyển thành `LLMError`, chỉ chứa loại lỗi và HTTP status. Không đưa provider body hoặc prompt
  vào thông báo lỗi. 401 thường liên quan key, 402 liên quan số dư, 429 liên quan giới hạn gọi API.
- Output rỗng, JSON lỗi, completion bị cắt hoặc stream không kết thúc đúng đều báo lỗi thay vì coi là thành công.

Trong ứng dụng FastAPI, lấy `ctx.llm` qua dependency `get_ctx` hiện có, tái sử dụng client đã tạo thay vì khởi tạo
mỗi request. Khi có key, `build_context()` tạo LLM client và đăng ký đóng bằng `ctx.register("llm", close=...)`.
Khi không có key, `ctx.llm` là `None`, API nền tảng vẫn chạy; service cần kiểm tra trường hợp này.

`/health` chỉ kiểm tra hạ tầng hiện có, **không kiểm tra key hoặc số dư LLM**. Health probe không gọi model để tránh
tiêu hao credits. App tắt sẽ đóng LLM client cùng các tài nguyên khác. Client truyền vào adapter để test do caller đóng.

Khi stream ra SSE hoặc dừng giữa chừng, dùng `aclosing` để giải phóng kết nối:

```python
from contextlib import aclosing

async def tokens(llm, messages):
    async with aclosing(llm.stream(messages)) as stream:
        async for token in stream:
            yield token
```

Nếu có lỗi sau vài token, giao diện phải đánh dấu câu trả lời chưa hoàn tất. Không tự retry cả stream rồi nối output
cũ với output mới. Usage hiện có trên kết quả gọi thường; `complete_json` và iterator stream chỉ trả dữ liệu nội dung.

## Docker

Service `api` trong `docker-compose.yml` nhận các biến DeepSeek/LLM từ `.env`. Bot và web không nhận API key này.
Sau khi thay `.env`, recreate container API để áp dụng. Không dùng `docker compose config` rồi chia sẻ output công khai,
vì Compose có thể render cả giá trị secret.

## API thử thinking và non-thinking

Từ thư mục `backend`, chạy trên cổng 8001:

```powershell
.\.venv\Scripts\python.exe -m uvicorn --factory app.main:create_app --host 0.0.0.0 --port 8001 --reload
```

Mở [Swagger](http://127.0.0.1:8001/api/docs), chọn `POST /api/v1/dev/llm/test`, bấm **Try it out**.
Hoặc dùng các request có sẵn trong `backend/scripts/deepseek_test.http` với REST Client của VS Code.

Body mẫu để thử non-thinking:

```json
{
  "message": "Godrick the Grafted là ai? Trả lời ngắn bằng tiếng Việt.",
  "thinking": false,
  "max_tokens": 2048,
  "temperature": 0.2
}
```

Giữ câu hỏi đó và đổi `thinking` thành `true`, thêm `"reasoning_effort": "low"` để thử thinking.
`temperature` không gửi tới provider trong chế độ thinking. Model luôn lấy từ `LLM_MODEL` trên server.
Giới hạn `max_tokens` gồm cả reasoning và câu trả lời, nên tăng giới hạn nếu bị báo `finish_reason=length`.

Phản hồi gồm `answer`, `reasoning_content` (nếu provider trả về), mode, model, `latency_ms` và `usage`.
`reasoning_content` là dữ liệu provider cho việc debug, không phải nguồn kiểm chứng đáp án.
`reasoning_tokens` là phần nằm trong `completion_tokens`, không cộng lần nữa vào `total_tokens`.
Khi provider không cung cấp thống kê reasoning, trường này là `null`.

Endpoint chỉ mount ở dev/test, không tồn tại khi `ENVIRONMENT=prod`. API tạm chưa dùng retrieval/RAG và chưa lưu
hội thoại. Mỗi lần Execute là một lượt gọi thật có dùng credits. Key chỉ đọc ở server, không gửi trong request từ Swagger.
503 nghĩa là client chưa có key, 502 là lỗi provider hoặc output chưa hoàn tất, 422 là body không hợp lệ.

Đã thử qua endpoint bằng key `.env` ngày 19/10/2026: cả hai mode trả HTTP 200. Với câu thử `2 + 2`, non-thinking
dùng 1 completion token, thinking dùng 43 completion token (41 reasoning token). Đây là một lượt kiểm tra kết nối,
không phải benchmark chất lượng hoặc tốc độ.

## Kiểm tra và phạm vi bàn giao

Test tại `backend/tests/unit/test_llm.py` dùng HTTP transport giả, bao gồm serialization, JSON, lỗi provider,
truncation, stream, đóng sớm, lỗi giữa stream, bảo vệ secret và đóng client theo vòng đời.
Chạy từ thư mục backend:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

Đã gọi thành công DeepSeek thật bằng key trong `.env` cho cả text, JSON và streaming ngày 19/10/2026.
Lượt text kiểm tra dùng 23 input token và 5 output token. Không lưu hoặc đưa key vào tài liệu.

Phần bàn giao là adapter LLM và cách tích hợp vòng đời app. `app/rag/generator.py`, retrieval, query rewriting và
endpoint chat vẫn cần được triển khai riêng trước khi có chatbot RAG trả lời từ kho nguồn.

## Tài liệu đối chiếu

- [DeepSeek API và model](https://api-docs.deepseek.com/)
- [JSON output](https://api-docs.deepseek.com/guides/json_mode/)
- [Thinking mode](https://api-docs.deepseek.com/guides/thinking_mode/)
