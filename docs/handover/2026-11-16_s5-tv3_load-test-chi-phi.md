# TV3 · Sprint 5: công cụ load test, chi phí LLM, p95 từng bước (16/11/2026)

Thẻ 5.7 (load test), 5.8 (chi phí LLM), 5.9 (eval trên cấu hình production). Yêu cầu: NFR-PERF-01, NFR-CAP-01, NFR-COST-01. Việc do agent của TV1 dựng hộ TV3, nhánh `feature/s5-tv3-load-test-chi-phi` (chưa push, chưa PR). **Chỉ dựng công cụ và tài liệu; chưa chạy gì với LLM thật hay server production, nên chưa có số đo NFR nào.**

## Phạm vi và file

| File | Nội dung |
|---|---|
| `backend/loadtest/locustfile.py` | Kịch bản Locust: SSE (đo TTFT và total), JSON, `/health`; câu hỏi từ golden set; think time; giữ hội thoại; `X-Service-Token` tùy chọn |
| `backend/loadtest/helpers.py` | Phần thuần (đọc golden set, đọc khung SSE, đọc biến môi trường), test được không cần locust |
| `backend/loadtest/README.md` | Lệnh chạy mock, staging, production; bảng biến môi trường |
| `backend/scripts/llm_cost.py` | Chi phí theo ngày từ `messages` + `rag_trace`, dự phóng 1.000 câu/ngày so với $30 |
| `backend/scripts/trace_latency.py` | p50/p95/max từng bước pipeline từ `rag_trace`, theo cửa sổ thời gian |
| `backend/tests/unit/test_s5_cost_and_latency.py` | 16 test cho ba phần trên (DB giả, không cần PostgreSQL/locust) |
| `docs/testing/s5-load-test-plan.md` | Phương pháp, kịch bản, ngưỡng đạt, cách chạy eval production và ghi `eval_runs`, bảng kết quả để trống |
| `docs/02_SRS.md` | Cập nhật ô trạng thái NFR-PERF-01, NFR-CAP-01, NFR-COST-01 (mỗi yêu cầu một dòng) |

`locust==2.46.7` đã có sẵn trong `requirements-dev.txt` và `constraints.txt`, không thay đổi phụ thuộc.

## Quyết định

- **Hai số đo cho mỗi lượt SSE**: dòng `POST /chat/stream [total]` (Locust mặc định chỉ tính tới khi có header nên ghi đè `response_time` bằng thời gian tới hết luồng) và dòng `[TTFT]` (tới event `token` đầu tiên, bắn bằng `events.request.fire`). Hệ quả: dòng `Aggregated` đếm mỗi lượt stream hai lần; kế hoạch yêu cầu đọc từng dòng riêng. Lượt không có token (câu ngoài phạm vi trả về một khối) không có dòng TTFT.
- **Lỗi = HTTP khác 200, event `error`, hoặc thiếu `done`**. 429 vì rate limit hiện ra là lỗi, không bị che.
- **Rate limit web theo IP (mặc định 10/phút)**: một máy Locust sẽ bị 429 ngay. Hai cách ghi trong README: nâng `RATE_LIMIT_PER_MINUTE` tạm thời, hoặc dùng `LOADTEST_SERVICE_TOKEN` (kênh discord, giới hạn theo `external_ref`).
- **Chi phí**: token lấy từ `messages.tokens_in/out` (đã là tổng sinh câu + agent + rewrite theo `app/rag/trace.py::token_usage`). Số lần Tavily ước tính từ `rag_trace`: số bước `tool_actions` có action `web_search`, nếu không có thì 1 khi `web_search.status` là `ok`/`error`. Đây là ước tính từ trace, chưa đối chiếu với hóa đơn Tavily. Giá mặc định (DeepSeek 0,28/0,42 USD/1M token, Tavily 0,008 USD/lượt) **chưa được đối chiếu với bảng giá hiện hành** (không có truy cập mạng để kiểm tra), ghi `TODO(verify)` trong code và bắt buộc truyền cờ giá khi báo cáo. Chưa tách token trúng cache của DeepSeek nên số đo là cận trên. Dự phóng = chi phí trung bình/câu của cửa sổ x 1.000 x 30; không có dữ liệu thì không báo "đạt".
- **p95 từng bước** dùng các khóa trace đang có: `prepare_ms`, `rewrite.elapsed_ms`, `agent.elapsed_ms`, tổng `retrieval_queries[].elapsed_ms`, `tool_actions[].elapsed_ms` theo action, và `generate_rest = latency_ms - prepare_ms` (suy ra). Không sửa code pipeline/generator (khóa của nhánh reranker): khi nhánh đó thêm bước đo mới (rerank, generate) vào trace, cần thêm vào `step_timings` một dòng. Trace bị cắt (>64 KB) chỉ góp cho `total`.
- Giữ nguyên `scripts/trace.py` và `scripts/eval_runs.py`; `trace_latency` dùng chung cách mở phiên DB và cửa sổ thời gian (`llm_cost.parse_window`).

## Kiểm tra đã chạy

- `ruff check .` -> All checks passed; `ruff format --check .` -> 280 files already formatted.
- `python -m pytest tests/unit -q` (backend/.venv) -> **1157 passed, 20 skipped**; riêng file mới: 16 passed.
- **Dry run mock (Locust 2.46.7 trong venv tạm, API mock `CHAT_MODE=mock` bằng uvicorn trên 127.0.0.1:18555, không Docker, không gọi mạng ngoài)**: 20 người dùng, 25 s, think 0,2-0,6 s: 1.249 request, 0 lỗi; `/chat` 237, `[total]` 468, `[TTFT]` 468 (p95 7-8 ms), `/health` 76 (mock không có Postgres/Redis nên trả 503 sau ~2 s, được chấp nhận bằng `LOADTEST_HEALTH_OK=200,503`). Xác nhận kịch bản chạy đúng và hội thoại được dùng lại; **số liệu này không có giá trị hiệu năng**. Server đã tắt sau khi chạy; thư mục CSV nằm ngoài repo.

## Sửa sau review

Review của TV1 lead, sửa trên cùng nhánh (commit riêng, chưa push):

1. **Đánh dấu lưu lượng load test**: `llm_cost` và `trace_latency` thêm `--include-loadtest`; mặc định join `conversations` và loại hội thoại có `external_ref` bắt đầu bằng `loadtest:` (hội thoại không có `external_ref` được giữ). README và kế hoạch ghi: production và đo sức chịu tải bắt buộc dùng chế độ service token; chế độ web không đánh dấu được nên chỉ dùng trên staging vắng người dùng thật.
2. **429 là lỗi riêng `rate_limited`** trong Locust cho `/chat` và `/chat/stream` (`helpers.failure_label`); README giải thích giới hạn theo IP.
3. **`parse_window`**: `--until` không kèm `--since` bị từ chối bằng thông báo rõ; giá trị có múi giờ đổi bằng `astimezone(UTC)`, giá trị không có múi giờ coi là UTC.
4. **`trace_latency.fetch_rows`** chỉ chọn hai cột `latency_ms` và `rag_trace` (không nạp cả `Message`).
- Test mới: 6 (tổng 22 trong `test_s5_cost_and_latency.py`); SQL của hai báo cáo được kiểm bằng biên dịch câu lệnh (cột chọn, JOIN, điều kiện `NOT LIKE 'loadtest:%'`), vẫn chưa chạy trên PostgreSQL thật.
- Quyết định từ TV1: không chạy gì thật; giữ `backend/loadtest/` là thư mục riêng.

## Chưa kiểm chứng

- Chưa chạy với `CHAT_MODE=rag`/`llm_only`, staging hay production (cần TV1 duyệt: tốn DeepSeek/Tavily, và staging nằm sau Caddy basic auth + danh sách IP). Chưa biết TTFT thực tế của stack.
- `llm_cost.py` và `trace_latency.py` chưa chạy trên PostgreSQL thật: truy vấn chỉ được kiểm bằng session giả (SQL biên dịch được, nhưng biểu thức JSONB `rag_trace["tool_actions"]` chưa chạy trên Postgres). Cần một lần chạy thử `--days 1` sau khi có DB.
- Chưa có test tích hợp ghi `eval_runs`; thẻ 5.9 chỉ có quy trình trong kế hoạch, chưa chạy full eval, chưa so với Sprint 4.
- Chưa làm các mục tối ưu của thẻ 5.7/5.8 (thread ONNX, semaphore rerank, top-N, cache Redis FR-CHAT-05, prompt caching, rút gọn ngữ cảnh): cần số đo trước, và nhiều mục nằm ở file bị khóa bởi nhánh reranker.

## Việc cần TV1 quyết định

1. Duyệt lần chạy staging 20 và 50 người dùng (ngày giờ, ngân sách DeepSeek/Tavily, cách xử lý rate limit).
2. Xác nhận bảng giá DeepSeek/Tavily hiện hành để điền vào cờ `--input-price/--output-price/--search-price`.
3. Chọn môi trường chạy eval 100 ca cho thẻ 5.9 và người chấm.
