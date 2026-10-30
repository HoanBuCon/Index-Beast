# Đo độ trễ HybridRetriever / Qdrant Query API

TV3 — MinhMuc, 31/10/2026 (Asia/Saigon). Nhánh `feature/s2-tv3-retrieval-latency`, từ develop `cf3c7ad`.
 Không gọi DeepSeek, không reindex hoặc ghi dữ liệu Qdrant.

## Phương pháp

[Script benchmark](../../backend/scripts/benchmark_retrieval.py) gọi native `HybridRetriever.retrieve()`;
wrapper đo encoder, `store.ready()` và đúng lời gọi `AsyncQdrantClient.query_points()`.
Giữ prefetch dense + sparse BM25 IDF, fusion RRF, filters và metadata round-trip của ứng dụng.

- Collection `indexbeast_tv3_integration_20261029_c1871afc`, **18.368 point**.
- FastEmbed `0.9.0`, ONNX Runtime `1.31.0`, qdrant-client `1.19.1`, Python `3.11.9`.
- E5 `intfloat/multilingual-e5-small` dense 384 cosine + sparse `Qdrant/bm25`; CPU Ryzen 7 5800H, 4 encoder thread.
- Qdrant Docker local; prefetch/fusion top-N **30**, không đổi settings hoặc `.env`.
- Policy `pilot/en`, game_scope base/elden_ring, source types và admission stamp hiện tại; spoilers=true.
  Toàn bộ filter JSON thực tế có trong report gốc. Không thử tất cả tổ hợp filter bằng benchmark này.
- Mười câu cố định: 5 VI + 5 EN, bao gồm nhân vật, quan hệ nhiều thực thể, mechanics, build, quest.
- Một cold request VI01 với encoder/client mới và model weights đã cache. Có precheck read-only trước request;
  không gọi đây là cold OS/disk/server cache. Lần load encoder đầu nằm trong embedding_ms.
- Sau đó cùng encoder/client, cùng thứ tự 10 câu × 3 vòng = **30 warm request**, concurrency 1.
  Không cache vector query ở script; mỗi request gọi encoder thật. Các câu và kết quả từng lượt nằm trong JSON.
- Không chạy unit tests đồng thời với benchmark. Máy không được cô lập khỏi mọi workload khác.

`qdrant_ms` là round-trip phía client, gồm transport/deserialize; không phải thời gian CPU server thuần.
`ready_ms` tách kiểm collection/schema. `total_retrieve_ms` bao gồm readiness, embedding, Query API,
LangChain, lọc policy và Document/Hit conversion. Không gồm rewrite, rerank, chọn context, HTTP chat API hoặc LLM.
Top-5 trong report chỉ là mẫu xem đầu kết quả top-30, không phải kết quả đã qua context budget/rerank.

Median dùng statistics.median; p95 dùng nearest rank `sorted[ceil(0.95*n)-1]`.
Lỗi được lưu riêng, không đưa vào thống kê thành công dưới dạng số 0; kết quả rỗng đếm riêng.

## Kết quả thực tế

Chạy lúc **00:00:46–00:00:49 ngày 31/10/2026**, status=complete, exit code 0.
[JSON gốc](2026-10-31_retrieval-latency.json) giữ số liệu chưa làm tròn.

| Warm, đơn vị ms | Min | Median | p95 | Max |
|---|---:|---:|---:|---:|
| Ready/schema check | 6,768 | 8,023 | 15,053 | 15,474 |
| Query embedding dense + sparse | 6,593 | 8,112 | 9,859 | 10,791 |
| Qdrant Query API round-trip | 11,657 | 12,921 | 33,119 | 34,476 |
| **Toàn bộ retrieve()** | **28,502** | **31,897** | **57,948** | **59,931** |

Các percentile của từng phase không cộng trực tiếp thành percentile tổng vì có thể thuộc các request khác nhau.
Phần overhead ngoài các phase vẫn nằm trong total_retrieve_ms.

| Lượt đầu, ms | Ready | Embedding, gồm load model | Qdrant | Toàn bộ retrieve |
|---|---:|---:|---:|---:|
| Cold VI01 | 12,609 | 1.684,957 | 108,334 | **1.855,147** |

Warm VI (15 mẫu): median **31,862 ms**, p95 **59,931 ms**.
Warm EN (15 mẫu): median **33,294 ms**, p95 **36,571 ms**.
Với chỉ 15 mẫu mỗi ngôn ngữ, nearest-rank p95 chính là max; chưa đủ để kết luận khác biệt ngôn ngữ tổng quát.

- Warm **30/30 thành công**, 0 lỗi, 0 kết quả rỗng; cold cũng thành công.
- Mỗi request có đúng **1 lời gọi Query API fusion**, trả 30 hit sau lọc policy.
- Count trước/sau **18.368 → 18.368**; benchmark chỉ gọi read-only readiness/count/query.
- Tổng wall của benchmark 3,358 giây, gồm prechecks và ghi report; không dùng số đó thay latency từng request.
- Không sửa `.env` hoặc artifact; không tải corpus mới, không gọi LLM, không upsert/drop/create collection.

## Nghiệm thu và giới hạn

Code hiện có đáp ứng dense+sparse prefetch/RRF/top-N cấu hình, metadata filters và unit collection nhỏ.
Phần bổ sung này cung cấp phép đo retrieval riêng cho checklist, không dùng thời gian chat/index thay thế.

SRS NFR-PERF-02 mô tả retrieval + rerank p95 ≤ 1 giây. Phép đo hiện tại chỉ có retrieval tuần tự;
**chưa kết luận đạt NFR đầy đủ**, chưa đo reranker/concurrency. P95 của 30 request trên máy local không phải SLA production.
FR-RET-05 trong SRS cũ còn yêu cầu base-only; pilot hiện theo quyết định corpus mở rộng của team,
không sửa SRS hay tự đổi filter về base để nghiệm thu hình thức. Spoiler thiếu nhãn không coi là an toàn;
chạy --no-spoilers có thể trả rỗng và không được diễn giải là lỗi tốc độ.

Không đánh giá Recall@K/MRR hoặc semantic correctness. Có 30 hit không chứng minh lấy đúng evidence;
RRF score không phải xác suất đúng. Cần golden set để đánh giá chất lượng độc lập.

## Tái lập

Từ backend; lệnh sau **đã chạy** với tên report mới, dùng query embedding thật và đọc Qdrant:

```powershell
.venv/Scripts/python.exe -u -X utf8 -m scripts.benchmark_retrieval --allow-inference --report ../docs/testing/2026-10-30_retrieval-latency.json
```

Tên report ban đầu đặt theo ngày 30/10; timestamp thực tế đã sang ngày 31/10 nên sau chạy đã đổi tên thành
`2026-10-31_retrieval-latency.json`, không sửa số đo hay chạy lại để thay kết quả.
Report không bị ghi đè; để chạy lại cần đổi tên JSON đích. Mặc định 3 vòng, có --rounds 1..20,
--limit 1..200 (mặc định Settings RAG_PREFETCH) và --no-spoilers. Không truyền --allow-inference thì dừng trước client/model.
Client đóng sau chạy, kể cả lỗi; lỗi đo/client cleanup làm status failed hoặc exit khác 0.
Chỉ ghi report vào đường dẫn ngoài source data, không đổi collection hay app behavior.

Handover ở [bàn giao retrieval latency](../handover/2026-10-31_s2-tv3_do-tre-retrieval.md).

Sau benchmark, unit suite: **323 passed, 1 warning**, 14,71 giây; gồm 6 case mới cho benchmark.
Warning dự kiến về payload indexes trong Qdrant memory. Ruff lint/format (163 file), OpenAPI,
UTF-8/local links và `git diff --check` đạt. Không đổi dependency nên không cài thư viện hoặc chạy lại pip check.
