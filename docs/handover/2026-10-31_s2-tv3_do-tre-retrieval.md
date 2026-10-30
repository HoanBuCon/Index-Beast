# Bàn giao đo độ trễ retrieval hybrid

TV3 — MinhMuc, nhóm 4 Hollows. Ngày 31/10/2026 (Asia/Saigon).
Nhánh `feature/s2-tv3-retrieval-latency` từ develop `cf3c7ad` sau PR #39.


## Thay đổi

- [benchmark_retrieval.py](../../backend/scripts/benchmark_retrieval.py): script read-only, flag --allow-inference,
  native HybridRetriever/Query API, đo ready/embedding/Qdrant/total; cold riêng, warm VI/EN, median/p95 nearest rank.
- [Unit tests](../../backend/tests/unit/test_retrieval_benchmark.py): guard trước client/model, thống kê không
  tính lỗi thành số 0, counter reset, instrumentation thiếu bị báo lỗi và đo đúng client query_points.
- [Báo cáo](../testing/2026-10-31_retrieval-latency.md), [JSON từng lượt](../testing/2026-10-31_retrieval-latency.json).
- Link trong RAG README và danh sách handover. Không đổi code retrieval/filter/index hoặc schema API.

## Đã chạy

Một encoder/client mới, weights E5 cached, 4 CPU thread, Qdrant local có 18.368 point,
prefetch dense+sparse và fusion RRF limit=30. Policy pilot/en, spoilers=true.
Một cold request; tiếp theo 10 câu (5 VI/5 EN) × 3 vòng tuần tự, cùng encoder/client.

| Chỉ số | Kết quả |
|---|---:|
| Cold total retrieve | 1.855,147 ms |
| Cold embedding, gồm load model | 1.684,957 ms |
| Warm total median / p95 | **31,897 / 57,948 ms** |
| Warm embedding median / p95 | 8,112 / 9,859 ms |
| Warm Query API median / p95 | 12,921 / 33,119 ms |
| Warm thành công / lỗi / rỗng | 30 / 0 / 0 |
| Count trước / sau | 18.368 / 18.368 |

Status complete và exit code 0. Không gọi LLM, notebook/crawl, reindex hoặc ghi collection/DB;
không sửa artifact, `.env` hoặc dependency. Benchmark đo lúc 00:00:46–00:00:49 ngày 31/10/2026.
Không trộn cold vào warm hoặc dùng thời gian chat/index làm latency retrieval.

## Cách dùng và giới hạn

Từ backend:

```powershell
.venv/Scripts/python.exe -u -X utf8 -m scripts.benchmark_retrieval --allow-inference --report ../docs/testing/retrieval-latency-rerun.json
```

Đây là hướng dẫn chạy lần tiếp theo (CPU query embedding thật, chỉ đọc server); cần report filename mới.
Script mặc định rounds=3, limit lấy RAG_PREFETCH, có --no-spoilers; đọc báo cáo để hiểu filter thiếu nhãn spoiler.
Client được cleanup khi kết thúc, không để model service hoặc background job chạy.

P95 là nearest rank, mẫu chỉ 30 warm request, chưa load test/concurrency; không chứng minh SLA production.
Đo Qdrant là client round-trip, không server CPU thuần; total không gồm rerank, rewrite, LLM hoặc HTTP chat API.
SRS NFR-PERF-02 bao gồm cả rerank, nên chưa tuyên bố hoàn thành NFR đó. FR-RET-05 base-only trong SRS cũ
cần nhóm đồng bộ với quyết định pilot corpus mở rộng. Không tự sửa SRS/ADR trong tác vụ này.
Không đo Recall@K/MRR, không khẳng định top-30 là đúng chỉ vì có kết quả; golden set đánh giá riêng.

## Kiểm thử offline

Full suite từ backend: **323 passed, 1 warning**, 14,71 giây; gồm 6 case mới cho benchmark.
Warning dự kiến về payload indexes của Qdrant memory. Ruff lint/format (163 file), OpenAPI,
UTF-8/local links và `git diff --check` đạt. Dependency không đổi, không chạy lại pip check.
Các unit test dùng fake hoặc Qdrant memory, không chạy benchmark inference thật qua pytest.

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest -c pyproject.toml tests/unit -q
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -X utf8 -m scripts.export_openapi --check
```
