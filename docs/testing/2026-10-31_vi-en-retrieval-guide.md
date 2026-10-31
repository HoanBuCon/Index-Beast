# Chẩn đoán và so sánh retrieval VI–EN

31/10/2026 · TV3 — MinhMuc · IndexBeast.

## Kết luận trong phạm vi offline

Pipeline trước đây có rewrite tùy chọn nhưng chỉ kiểm schema/số liệu, thay query gốc bằng query mới rồi
truy xuất một lần. Chưa có guard tên riêng/mục tiêu, timeout riêng hoặc phép so sánh VI–EN có ghép cặp.
Khi rewrite tắt, câu tiếng Việt đi thẳng đến dense và BM25 trên corpus được chọn.
Điều này là giả thuyết hợp lý cho chênh lệch ngôn ngữ, **chưa phải phép đo recall thực tế**.

Không kết luận E5 hỏng, dataset thiếu hoặc JSON lỗi vì tiếng Việt. Source có thể thiếu nội dung, query có thể
lấy lệch đoạn, hoặc generator có thể từ chối sai; cần xem từng tầng trong report sau khi người dùng chạy thật.

## Đã triển khai

- Ngôn ngữ trả lời vẫn lấy từ request/language detection. Query tiếng Anh không đổi answer tiếng Việt sang tiếng Anh;
  trường lang do rewrite trả về không được ghi đè ngôn ngữ server đã chọn.
- Rewrite một logical call, non-thinking, tối đa 512 output token và await 8 giây mặc định.
  Guard schema, tên bề mặt xuất hiện trong question/history, số liệu không mất/thêm ngoài user history,
  PvE/PvP/NG+, cùng một số mẫu comparison/acquisition/build/strategy/negation.
- Prompt không tự dịch biệt danh chưa có mapping được xác minh. Cho phép tên tiếng Anh người dùng ghi rõ trong ngoặc;
  không tạo bảng tên dịch/biệt danh chuẩn từ phỏng đoán. History giữ đúng role, chỉ dùng để giải tham chiếu.
- Rewrite lỗi/rỗng/mất constraint/quá hạn quay về câu gốc. Đại từ chưa có referent và không history vẫn hỏi làm rõ,
  kể cả khi rewrite lỗi, không đoán thực thể để đi tìm.
- `RAG_QUERY_MODE=rewrite`: một query (mặc định). `dual`: query EN và query gốc khác nhau, tối đa hai query tuần tự;
  khi rewrite tắt/lỗi hoặc query trùng thì chỉ một query. Dual giữ cơ hội lấy evidence theo tên/từ gốc nếu rewrite chưa tốt.
- Dual gộp **thứ hạng** bằng RRF `sum(1/(60+rank))`, không cộng score native. Một point chỉ góp một lần mỗi query.
  Có tối đa rag_prefetch ứng viên mỗi query và tối đa rag_prefetch sau fusion; context vẫn tối đa 5.
- Loại point trùng và chunk text giống hệt có cùng provenance/section/conditions/release/type/review/image metadata.
  Không semantic dedup, không cap một chunk mỗi trang vì câu hỏi nhiều bước có thể cần nhiều đoạn cùng trang.
  Thiếu source_id/revision thì không tự kết luận hai chunk là trùng nội dung.
- Await budget retrieval mặc định 20 giây, chia đều cho số query. Một query lỗi có thể dùng kết quả query kia;
  tất cả lỗi vẫn báo unavailable, không biến thành insufficient. Ngân sách là thời gian await, không bảo đảm dừng ngay
  công việc CPU đang chạy trong worker của encoder.

Đây là guard bề mặt và mẫu từ, không phải NER/semantic verifier. Có thể fallback quá thận trọng khi model đổi cách
viết tên/số; kiểm benchmark trước khi nới rule. Reranker vẫn là NoReranker nếu chưa inject implementation khác.
Không thêm model, thay embedding/ID/collection hoặc tăng temperature để chữa retrieval.

## Cấu hình ứng dụng — người dùng tự bật

Không sửa `.env` thật trong tác vụ này. Defaults và `.env.example` giữ rewrite **false**, mode **rewrite**.
Để thử một phiên API mà không sửa file, dừng API cũ tại terminal của nó; từ gốc project dùng PowerShell:

```powershell
$env:RAG_REWRITE_ENABLED="true"
$env:RAG_QUERY_MODE="rewrite"
make api
```

Muốn so sánh dual thì đổi RAG_QUERY_MODE thành `dual` trong phiên thử rồi restart API.
Sau khi thử có thể xóa override:

```powershell
Remove-Item Env:RAG_REWRITE_ENABLED
Remove-Item Env:RAG_QUERY_MODE
```

Các biến mới có trong Compose/.env.example:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| RAG_QUERY_MODE | rewrite | rewrite hoặc dual |
| RAG_REWRITE_TIMEOUT_SECONDS | 8 | Await deadline cho rewrite, >0 đến 60 |
| RAG_REWRITE_MAX_TOKENS | 512 | Budget rewrite, 128 đến 2048 |
| RAG_RETRIEVAL_TIMEOUT_SECONDS | 20 | Await budget retrieval, >0 đến 120 |

Bật rewrite có thể thêm một logical LLM call; dual có thể thêm một lần query embedding và Qdrant.
SDK transport retry có thể tạo nhiều HTTP attempt cho một logical call. Rewrite không dùng generation-format retry.
Giữ thinking/temperature của generation theo cấu hình đang có. Không cần reindex cho thay đổi này.

## Bộ câu hỏi và nhãn

[vi_en_pairs.jsonl](../../backend/eval/vi_en_pairs.jsonl): **13 cặp, 26 câu, 50% VI**.
Bao gồm lore, mechanics, acquisition, quest, boss strategy, build, comparison, history follow-up,
tên được người dùng ghi rõ, nickname chưa xác minh, đại từ mơ hồ, private-mod thiếu evidence và ngoài phạm vi.

Tất cả review_status=pending, expected_chunk_ids rỗng. Đã đối chiếu URL target của năm trang thực thể
Ranni/Bloodhound's Fang/Uchigatana/Malenia/Rivers of Blood với artifact local chỉ đọc; chưa chứng nhận chunk
của trang đó chứa đáp án hoặc câu VI/EN đã được TV2 review tương đương ngữ nghĩa.
P09 là tên được người dùng cung cấp rõ, không phải xác nhận một biệt danh cộng đồng.

`source_targets` chỉ là trang cần khảo sát, không phải evidence labels. Không thay đổi golden_set.jsonl 60 câu hiện có.
TV2 cần review câu song song và gắn artifact chunk UUID thật chứa evidence trước khi đặt review_status=reviewed.
Không tự gán reviewed/approved để có điểm recall.

## Benchmark — mặc định không thực thi model/server

Từ `backend/`, lệnh **đã chạy**:

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.benchmark_vi_en --strategies original rewrite dual
```

Kết quả plan-only: 13 cặp, 78 dòng, tối đa 52 logical rewrite call và 104 retrieval query nếu thực thi đủ ba chiến lược.
Không tạo client/encoder/model, không kết nối server, không ghi report hoặc dữ liệu. Đây không phải kết quả benchmark.

Các lệnh sau **chỉ hướng dẫn, chưa chạy**. `--execute` cho phép query embedding và đọc Qdrant;
cache E5 phải có, nếu thiếu có thể tải model. Có thể đặt `HF_HUB_OFFLINE=1` để yêu cầu dùng cache local.
`--allow-llm` cho phép API trả phí. Output phải là file .json mới trong thư mục đã có, ngoài backend/data.

Thử cặp P02 với query gốc trước, không LLM:

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.benchmark_vi_en --pair-id P02 --strategies original --execute --output ../docs/testing/vi-en-original-p02.json
```

So sánh ba chiến lược cho cùng cặp, có gọi rewrite thật:

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.benchmark_vi_en --pair-id P02 --strategies original rewrite dual --execute --allow-llm --output ../docs/testing/vi-en-compare-p02.json
```

Thêm generation để đọc answer/context và phân biệt output error với insufficient:

```powershell
.venv/Scripts/python.exe -X utf8 -m scripts.benchmark_vi_en --pair-id P02 --strategies rewrite --execute --allow-llm --generate --output ../docs/testing/vi-en-answer-p02.json
```

Bỏ `--pair-id P02` khi đã kiểm ngân sách và muốn chạy đủ bộ.
Script chỉ đọc collection hiện có, không upsert/create/drop/index. Benchmark overrides cấu hình pipeline trong RAM,
không đổi `.env` hoặc mode API đang chạy. Client được đóng trong finally. Không tự ghi đè report cũ.

## Đọc report đúng

- Rewrite: trạng thái, lý do fallback, thời gian/usage. Query thực dùng chỉ lưu khi benchmark opt-in diagnostic_queries;
  không log query/history vào application log hoặc trace mặc định của API.
- Retrieval: query kind, elapsed, success/error và ứng viên trước context. Query gốc/rewritten được lưu trong report
  để review tên/tham số/ý định; không đưa report câu hỏi riêng tư lên Git tùy tiện.
- `candidate_source_hit`, `top5_source_hit`: có lấy được trang target không, **không chứng minh đúng evidence**.
- Evidence recall: chỉ tính khi có expected_chunk_ids đã review; bộ v0 hiện để null, không đánh 0/1 giả.
- Generation: `not_run`, hoặc `ok` với outcome static/grounded/insufficient, hoặc error kèm mã format/validation.
  Insufficient là kết quả có chủ đích, khác JSON lỗi hoặc retrieval unavailable.
- Correctness, faithfulness và giữ ý định rewrite: manual_review ban đầu null, phải đọc answer cùng context để chấm.

Benchmark gọi pipeline trực tiếp, không đo HTTP API status hoặc UI/Discord. Không gán một lỗi JSON cho ngôn ngữ đầu vào
chỉ dựa vào số lần lỗi. Cần ghép cặp cùng ý hỏi, đọc từng tầng và review evidence.

## Kiểm tra offline đã chạy

Baseline **429 passed, 1 warning**, 17,97 giây; kết thúc **467 passed, 1 warning**, 16,56 giây (thêm 38 case).
Không dùng thời gian pytest làm benchmark retrieval. Warning Qdrant memory về payload index là dự kiến.
Ruff check/format trên 6 file Python của tác vụ, OpenAPI check, pip check và plan-only đạt.
Test dùng fake LLM/retriever/ranking, không chạy encoder hoặc model/server thật; không có điểm recall thực tế mới.
Giữ các regression JSON/SSE/citation/ảnh/ba mode đã có. Chưa xác định mức cải thiện trên corpus thật.
