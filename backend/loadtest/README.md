# Load test IndexBeast (Locust)

Kịch bản: `loadtest/locustfile.py`. Phương pháp, ngưỡng đạt và bảng kết quả: [docs/testing/s5-load-test-plan.md](../../docs/testing/s5-load-test-plan.md).

Mỗi người dùng ảo lặp: hỏi một câu lấy ngẫu nhiên từ golden set (`eval/golden_set.jsonl` + `eval/golden_set_s3.jsonl`,
khoảng 300 câu Việt/Anh), nghỉ 5-20 giây, hỏi tiếp trong cùng hội thoại (đổi hội thoại sau 4 lượt).

| Tác vụ | Tỉ trọng | Tên trong báo cáo |
|---|---|---|
| `POST /api/v1/chat/stream` (SSE) | 6 | `POST /chat/stream [total]` (tới khung `done`) và `POST /chat/stream [TTFT]` (tới token đầu tiên) |
| `POST /api/v1/chat` (JSON, kiểu bot) | 3 | `POST /chat` |
| `GET /api/v1/health` | 1 | `GET /health` |

Dòng `[TTFT]` là số đo thêm trên cùng request SSE nên dòng `Aggregated` đếm mỗi lượt stream hai lần: chỉ đọc từng dòng riêng.

## Cài đặt

```powershell
cd backend
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt -c constraints.txt   # có locust==2.46.7
```

Luôn chạy từ thư mục `backend/` bằng `python -m locust` (để import được `loadtest.helpers`).

## Biến môi trường

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `LOADTEST_GOLDEN` | 2 file golden ở trên | Đường dẫn JSONL, cách nhau bằng dấu phẩy |
| `LOADTEST_THINK_MIN` / `LOADTEST_THINK_MAX` | 5 / 20 | Giây nghỉ giữa hai tác vụ |
| `LOADTEST_TURNS_PER_CONVERSATION` | 4 | Số lượt trước khi mở hội thoại mới |
| `LOADTEST_SERVICE_TOKEN` | trống | Có giá trị = gửi `X-Service-Token`, `channel=discord` + `external_ref` riêng mỗi hội thoại (giả lập bot) |
| `LOADTEST_WEB_SEARCH` | trống | `off`/`auto`/`always` gửi trong `options.web_search`; trống = theo cấu hình server |
| `LOADTEST_HEALTH_OK` | `200` | Mã HTTP coi là đạt cho `/health`; mock không có Postgres/Redis nên đặt `200,503` |
| `LOADTEST_TIMEOUT` | 60 | Timeout mỗi request (giây) |

Không đặt token vào dòng lệnh được ghi lại: đặt biến môi trường trong phiên shell (`$env:LOADTEST_SERVICE_TOKEN = ...`).

## 1. Local, mock (không tốn tiền)

Terminal 1 (API mock, không cần Docker; `/health` sẽ 503 vì không có Postgres/Redis/Qdrant):

```powershell
cd backend
$env:CHAT_MODE = "mock"
.venv/Scripts/python.exe -X utf8 -m uvicorn --factory app.main:create_app --host 127.0.0.1 --port 18000 --no-access-log
```

Terminal 2 (20 người dùng, tăng 10/giây, chạy 60 giây, think time ngắn để thử nhanh):

```powershell
cd backend
$env:LOADTEST_THINK_MIN = "0.2"; $env:LOADTEST_THINK_MAX = "0.6"; $env:LOADTEST_HEALTH_OK = "200,503"
.venv/Scripts/python.exe -X utf8 -m locust -f loadtest/locustfile.py --host http://127.0.0.1:18000 `
  --headless -u 20 -r 10 -t 60s --csv ../docs/testing/NEW_mock-20u
```

Mock trả cả câu cùng lúc nên TTFT gần bằng total; chỉ dùng để kiểm kịch bản chạy đúng, không phải số đo hiệu năng.

## 2. Staging (CHAT_MODE=rag, gọi DeepSeek/Tavily thật: cần TV1 duyệt)

Staging nằm sau Caddy basic auth và danh sách IP ([docs/staging.md](../../docs/staging.md)): chạy Locust từ IP đã được
phép hoặc từ chính VPS. Trước khi chạy, báo TV1 ngày giờ và ngân sách (xem mục chi phí trong kế hoạch).

```powershell
cd backend
.venv/Scripts/python.exe -X utf8 -m locust -f loadtest/locustfile.py --host https://<staging-host> `
  --headless -u 20 -r 2 -t 10m --csv ../docs/testing/NEW_staging-20u
.venv/Scripts/python.exe -X utf8 -m locust -f loadtest/locustfile.py --host https://<staging-host> `
  --headless -u 50 -r 2 -t 10m --csv ../docs/testing/NEW_staging-50u
```

### Hai chế độ lưu lượng (quan trọng)

- **Chế độ service token (`LOADTEST_SERVICE_TOKEN` đặt)**: kênh `discord`, giới hạn tần suất theo `external_ref`, và mỗi hội
  thoại có `external_ref` bắt đầu bằng `loadtest:`. Tiền tố này là dấu để `scripts.llm_cost` và `scripts.trace_latency` loại
  lưu lượng load test khỏi số liệu thật (mặc định loại; thêm `--include-loadtest` để tính cả). **Mọi lần chạy production và
  mọi lần đo sức chịu tải (NFR-PERF-01, NFR-CAP-01) PHẢI dùng chế độ này.**
- **Chế độ web (không token)**: kênh `web`, không có `external_ref` nên **không đánh dấu được**: hội thoại lẫn vào số liệu chi
  phí/độ trễ thật. Chỉ dùng trên staging, và chỉ khi cửa sổ thời gian không có người dùng thật.
- Giới hạn `/chat` theo IP (`RATE_LIMIT_PER_MINUTE`, mặc định 10, tối đa 1000) áp dụng cho chế độ web: mọi người dùng ảo cùng
  một IP (20 người dùng ảo tạo khoảng 90 request/phút) sẽ nhận 429. Trên staging, nâng `RATE_LIMIT_PER_MINUTE` tạm thời rồi
  hoàn lại, hoặc chuyển sang chế độ service token (giới hạn theo `external_ref`, mỗi hội thoại một khóa, không cần đổi cấu hình).
- Locust coi mọi mã khác 200 là lỗi. **429 được báo thành lỗi riêng tên `rate_limited`** (cột `Name`/`Error` của
  `_failures.csv`), tách khỏi `HTTP 5xx`/`SSE error`, cho `/chat` và `/chat/stream`. Số đo có `rate_limited` không phải số đo
  độ trễ: sửa cách chạy rồi chạy lại.

## 3. Production (chỉ khi TV1 duyệt, ngoài giờ cao điểm)

Cùng lệnh như staging với `--host https://<production-host>`, bắt đầu bằng `-u 5 -t 2m` để kiểm tra rồi mới lên 20 và 50.
Dừng ngay (Ctrl+C) nếu tỉ lệ lỗi > 5% hoặc `/health` báo `degraded`.

## Xem kết quả

`--csv <tiền-tố>` ghi `<tiền-tố>_stats.csv` (p50/p95/p99 mỗi dòng), `_stats_history.csv`, `_failures.csv`. Thêm `--html báo-cáo.html`
nếu muốn biểu đồ. Số đo cần ghi: p95 của dòng `[TTFT]` và `[total]`, tỉ lệ lỗi, req/s. Độ trễ từng bước phía server lấy bằng
`python -m scripts.trace_latency` (xem kế hoạch).
