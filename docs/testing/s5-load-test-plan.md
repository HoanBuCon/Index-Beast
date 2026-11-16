# Kế hoạch load test, chi phí LLM và eval production (Sprint 5)

Thẻ 5.7, 5.8, 5.9. Yêu cầu: NFR-PERF-01, NFR-CAP-01, NFR-COST-01. Công cụ do TV1 dựng hộ TV3; **chưa có số đo nào**, mọi bảng kết quả bên dưới để trống. Chạy thật gọi DeepSeek/Tavily và tốn tiền nên cần TV1 duyệt từng lần.

## 1. Tiêu chí đạt

| Mã | Điều kiện | Số đo | Ngưỡng |
|---|---|---|---|
| NFR-PERF-01 | <= 20 người dùng đồng thời | p95 `POST /chat/stream [TTFT]` | <= 3,5 s |
| NFR-PERF-01 | <= 20 người dùng đồng thời | p95 `POST /chat/stream [total]` và `POST /chat` | <= 10 s |
| NFR-CAP-01 | 50 người dùng đồng thời | tỉ lệ lỗi (HTTP != 200, SSE `error`, thiếu `done`) | 0 (xếp hàng được: chấp nhận chậm hơn, không chấp nhận lỗi) |
| NFR-COST-01 | 1.000 câu/ngày | chi phí/câu x 1.000 x 30 | <= $30/tháng |

p95 lấy từ cột 95% của `_stats.csv`, mỗi dòng riêng; không dùng dòng `Aggregated` (mỗi lượt SSE được ghi hai dòng). Lượt có 429 hay 5xx tính là lỗi, không loại khỏi mẫu.

## 2. Phương pháp

- Công cụ: Locust 2.46.7, kịch bản `backend/loadtest/locustfile.py`, lệnh cụ thể trong [backend/loadtest/README.md](../../backend/loadtest/README.md).
- Câu hỏi: lấy ngẫu nhiên từ golden set (`golden_set.jsonl` + `golden_set_s3.jsonl`, câu Việt và Anh). Mỗi người dùng ảo nghỉ 5-20 s giữa các tác vụ và giữ hội thoại 4 lượt (dùng lại `conversation_id`/`conversation_token`), nên có cả câu tiếp nối, không chỉ câu độc lập.
- Tỉ trọng: 60% SSE, 30% JSON, 10% `/health`.
- Mỗi cấu hình chạy 10 phút sau khi tăng tải (`-r 2`), bỏ 2 phút đầu khi đọc số đo (cache lạnh, model nạp lần đầu). Lặp lại tối thiểu 2 lần ở các thời điểm khác nhau; ghi cả hai, báo cáo lần xấu hơn.
- Cố định các biến khi so trước/sau tối ưu: cùng commit ngoài thay đổi đang đo, cùng collection Qdrant, cùng `CHAT_MODE=rag`, cùng `LOADTEST_WEB_SEARCH`, cùng host. Mỗi lần chỉ đổi một thứ (số thread ONNX, semaphore rerank, top-N, cache Redis...) và giữ lại thay đổi chỉ khi p95 cải thiện vượt độ nhiễu giữa hai lần chạy cùng cấu hình.
- Giới hạn tần suất: web giới hạn theo IP (mặc định 10/phút) nên một máy chạy Locust sẽ nhận 429. Dùng `LOADTEST_SERVICE_TOKEN` (giới hạn theo hội thoại) hoặc nâng `RATE_LIMIT_PER_MINUTE` tạm thời, và ghi lựa chọn vào cột Ghi chú.
- Máy chạy Locust phải có CPU rảnh (xem `Locust` cảnh báo CPU > 90%) và đặt cùng vùng mạng với server khi có thể; ghi băng thông/độ trễ mạng nếu chạy từ xa.

## 3. Kịch bản

| Kịch bản | Người dùng | Lệnh (rút gọn) | Mục đích |
|---|---|---|---|
| Mock dry-run | 20 | `-u 20 -r 10 -t 60s` với `CHAT_MODE=mock` | Kiểm kịch bản, không đo hiệu năng, không tốn tiền |
| Smoke staging | 5 | `-u 5 -r 1 -t 2m` | Kiểm kết nối, auth, rate limit trước khi lên tải |
| Tải chuẩn | 20 | `-u 20 -r 2 -t 10m` | NFR-PERF-01 |
| Tải đỉnh | 50 | `-u 50 -r 2 -t 10m` | NFR-CAP-01 |
| Bot | 20 | như tải chuẩn, thêm `LOADTEST_SERVICE_TOKEN` | Đường bot (`channel=discord`, JSON, giới hạn theo `external_ref`) |

Ngân sách: mỗi lượt RAG tốn khoảng chi phí/câu đo được ở mục 5; 20 người dùng trong 10 phút ≈ 600-900 câu. Nhân với chi phí/câu ước tính trước khi xin duyệt, và đặt trần bằng `-t` ngắn hơn khi chạy thử.

## 4. Đo p95 từng bước từ trace

Locust chỉ thấy độ trễ ngoài cùng. Sau mỗi lần chạy, lấy phân rã phía server từ trace đã lưu (FR-EVAL-05) trong đúng cửa sổ thời gian của lần chạy (UTC):

```powershell
cd backend
.venv/Scripts/python.exe -X utf8 -m scripts.trace_latency --since 2026-11-18 --until 2026-11-19 --limit 5000
.venv/Scripts/python.exe -X utf8 -m scripts.trace_latency --days 1 --json > ../docs/testing/NEW_steps-20u.json
```

Bước báo cáo: `total`, `prepare`, `rewrite`, `agent_decision`, `retrieval`, `tool:<action>` (nhất là `tool:web_search`), `generate_rest` (= total - prepare). Các bước chồng nhau nên không cộng lại. Cửa sổ phải hẹp (không lẫn lưu lượng người thật); nếu cần, dùng `--since/--until` theo ngày và ghi giờ chạy. Số bước là p95 theo từng bước độc lập, không phải phân rã của đúng một request. Bước nào chiếm p95 lớn nhất là ứng viên tối ưu đầu tiên (thread ONNX, semaphore rerank, top-N, cache Redis cho câu lặp FR-CHAT-05).

## 5. Chi phí LLM (thẻ 5.8, NFR-COST-01)

```powershell
cd backend
.venv/Scripts/python.exe -X utf8 -m scripts.llm_cost --days 7 --input-price <USD/1M> --output-price <USD/1M> --search-price <USD/lượt>
```

In số câu, token vào/ra, số lần tìm web và USD theo ngày (UTC), rồi chi phí/câu và dự phóng 1.000 câu/ngày x 30 ngày so với $30. Giá mặc định trong script (DeepSeek 0,28/0,42 USD mỗi triệu token, Tavily 0,008 USD/lượt) chỉ là điểm xuất phát chưa đối chiếu: **kiểm tra bảng giá hiện hành rồi truyền cờ giá**, và ghi giá đã dùng cùng ngày kiểm tra vào báo cáo. Lưu ý:

- Token lấy từ cột `messages.tokens_in/out` (tổng mọi lượt gọi LLM của câu trả lời). Câu trả lời lấy từ bộ nhớ đệm hoặc có sẵn có token NULL và tính 0 token.
- Chưa tách token trúng cache của nhà cung cấp (giá rẻ hơn), nên số đo là cận trên khi có prompt caching.
- Lưu lượng load test và lưu lượng thật nằm chung bảng. Chạy `llm_cost` với cửa sổ chỉ gồm lần load test để biết chi phí lần đó; chi phí/câu của golden set không đại diện cho câu hỏi thật.
- Dự phóng giả định mọi câu đắt như trung bình của cửa sổ; không tính Qdrant/VPS/embedding (chạy local).

## 6. Eval trên cấu hình production (thẻ 5.9)

Mục đích: so với Sprint 4 ([100 ca](2026-11-14_s4-evaluation-100.md): Answer Accuracy 85,54%, hành vi đúng 88,24%, bám nguồn 87,64%, p50/p95 9,68/20,73 s; ghi chú S4 chạy bốn runner song song) trên đúng cấu hình sẽ phát hành.

1. Chốt cấu hình: commit, `CHAT_MODE=rag`, model, reranker, collection Qdrant, `WEB_SEARCH_MODE`, các `RAG_*`. Ghi git SHA và `docker compose config` đã che secret vào báo cáo.
2. Chạy manifest 100 ca của S4 (`backend/eval/s4_evaluation_100.json`) bằng runner/đường chấm S4, qua HTTP vào server production hoặc staging cùng cấu hình (xem [báo cáo S4](2026-11-14_s4-evaluation-100.md) và [hướng dẫn chẩn đoán](../evaluation/golden-diagnostic-guide.md) cho lệnh runner; mỗi lệnh `--execute` là một lượt tốn API, không tự retry cả bộ). Chạy một runner tuần tự để p95 không bị nhiễu bởi chạy song song, và nêu khác biệt đó khi so với S4.
3. Chấm theo rubric S4, xuất `report.json`/điểm từng ca vào thư mục mới `docs/testing/NEW_s5-evaluation-100*`.
4. Ghi `eval_runs` (cần PostgreSQL đã migrate; dùng đúng `DATABASE_URL` của môi trường muốn ghi):

```powershell
cd backend
.venv/Scripts/python.exe -X utf8 -m scripts.eval_runs add --name s5-production-100 `
  --config model=<model> --config chat_mode=rag --config collection=<collection> --config env=production `
  --metric answer_accuracy=<0-1> --metric behavior_pass=<0-1> --metric grounded=<0-1> `
  --metric latency_p50_s=<s> --metric latency_p95_s=<s> --metric answered=<so-ca>
.venv/Scripts/python.exe -X utf8 -m scripts.eval_runs list --limit 5
```

   Số đo phải là số hữu hạn (không chuỗi/bool). Cũng ghi lượt S4 để so sánh nếu chưa có (`--name s4-100 --git-sha <sha>`), với đúng các tên metric trên.
5. Dán số vào bảng 7.3 và nêu rõ ca nào xấu đi so với S4.

## 7. Bảng kết quả (điền sau khi chạy)

### 7.1 Load test (Locust)

| Ngày | Môi trường | Commit | Người dùng | Phút | Req | Lỗi (%) | TTFT p50 / p95 (s) | Total p50 / p95 (s) | req/s | Đạt? | Ghi chú (rate limit, token bot, cấu hình) |
|---|---|---|---:|---:|---:|---:|---|---|---:|---|---|
| | | | 20 | 10 | | | | | | | |
| | | | 50 | 10 | | | | | | | |
| | | | 20 (bot) | 10 | | | | | | | |

### 7.2 p95 từng bước (từ `scripts.trace_latency`)

| Bước | n | p50 (ms) | p95 (ms) | Trước tối ưu | Sau tối ưu | Giữ/hoàn lại |
|---|---:|---:|---:|---:|---:|---|
| total | | | | | | |
| prepare | | | | | | |
| rewrite | | | | | | |
| agent_decision | | | | | | |
| retrieval | | | | | | |
| tool:web_search | | | | | | |
| generate_rest | | | | | | |

### 7.3 Chi phí và eval

| Mục | S4 (đã đo) | S5 production |
|---|---|---|
| Chi phí/câu (USD) | chưa đo | |
| Dự phóng 1.000 câu/ngày (USD/tháng, mục tiêu <= 30) | chưa đo | |
| Giá dùng (vào / ra / tìm web) và ngày kiểm tra | - | |
| Answer Accuracy | 85,54% | |
| Hành vi đúng | 88,24% | |
| Bám nguồn | 87,64% | |
| Độ trễ ca p50 / p95 | 9,68 s / 20,73 s | |
| `eval_runs` id | - | |

### 7.4 Nhật ký tối ưu (kể cả thay đổi đã hoàn lại)

| Ý tưởng | Trước -> Sau | Kết luận | Lý do |
|---|---|---|---|
| | | | |

## 8. Cái công cụ này không đo

- Độ trễ trình duyệt/hiển thị (chỉ đo tới khung `done`), độ chính xác của câu trả lời khi tải cao (đã có eval 5.9; để kiểm tra suy giảm chất lượng dưới tải, chạy lại một phần golden set sau lần 50 người dùng).
- Locust và server cùng máy làm số đo sai; không dùng số đo local làm bằng chứng NFR.
- Câu hỏi golden set lặp lại có thể trúng cache (khi FR-CHAT-05 hoàn tất), làm p95 đẹp hơn thực tế: nếu bật cache, đo cả có cache và `LOADTEST_GOLDEN` trỏ tới bộ câu đã biến đổi.
