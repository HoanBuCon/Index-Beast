# Bàn giao đo thời gian index toàn bộ

Ngày 30/10/2026 (Asia/Saigon), TV3 — MinhMuc, nhóm 4 Hollows.
Nhánh `feature/s2-tv3-full-index-benchmark`, từ develop `dbc6c6f`.

## Thay đổi

- Thêm [script benchmark](../../backend/scripts/benchmark_index.py): gọi native `index_chunks`, đo tách
  preflight/index/embedding/upsert/verification/total, ghi progress/report JSON atomic.
- Thêm [unit test offline](../../backend/tests/unit/test_index_benchmark.py) cho flag quyền ghi,
  counter chỉ tăng sau thành công và progress report bằng encoder/client giả, vector tổng hợp.
- [Báo cáo và cách tái lập](../testing/2026-10-30_full-index-benchmark.md),
  [JSON số liệu](../testing/2026-10-30_full-index-benchmark.json).
- Không đổi index admission, schema, thuật toán ID, model, artifact, `.env` hoặc logic chatbot.

## Kết quả và kiểm chứng

**Đã hoàn tất**, JSON status=complete, tiến trình exit code 0. Không bị ngắt hoặc resume giữa lượt đo.

- Lượt index đầy đủ: **999,802 giây (~16 phút 40 giây)**, 18,372 chunk/giây.
- Tổng gồm preflight và xác minh/cleanup: **1.009,263 giây (~16 phút 49 giây)**.
- Embedding 962,445 giây; upsert 36,692 giây; preflight 9,011 giây.
- Encode và upsert đủ 18.368 bản ghi, 2.296 batch. Count trước/sau 18.368, không tăng point.
- Payload 8 mẫu khớp input và giữ nguyên so với trước, gồm timestamp. Không gọi đó là đối chiếu toàn bộ payload/vector.
- Hash source giữ nguyên: `95794a89485e6f86ff320ee9b2a9a707a794e1bdc040162f0b41e5b2c208d03e`.
- Preflight re-encode bằng tokenizer E5 local trên artifact: invalid 0. Không gọi LLM.
- Docker Desktop ban đầu tắt, đã khởi động và bảo đảm Qdrant healthy trước khi bấm giờ.
  Thời gian khởi động Docker không nằm trong benchmark. Giữ Docker/collection sau khi chạy để phục vụ demo.

Sau benchmark đã chạy từ backend:

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest -c pyproject.toml tests/unit -q
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -X utf8 -m scripts.export_openapi --check
```

**317 passed, 1 warning**, 15,90 giây; gồm 5 case mới cho benchmark, không inference/network thật trong unit tests.
Warning dự kiến về payload indexes của Qdrant memory. Ruff/format (161 file), OpenAPI, UTF-8/local links và
`git diff --check` đạt. Không thêm dependency. Không chạy unit suite đồng thời với phép đo embedding.

Phạm vi full là toàn bộ 18.368 chunk EN được policy pilot/en chọn trong artifact 23.765 chunk;
5.397 chunk ngôn ngữ khác không chọn, không coi đó là lỗi index.
Đây là re-embedding/upsert vào collection hiện có, không phải cold download hoặc build collection rỗng.
Model weights cache có sẵn; lần load encoder đầu nằm trong thời gian index/embedding.

## Cách dùng và việc còn lại

Chạy lại benchmark cần `--allow-write` và report JSON mới; xem lệnh trong báo cáo.
Không cần reindex chỉ để demo. Dùng `make dev` khi Docker sẵn sàng và cấu hình key/collection còn đúng.
Phép đo không xác minh semantic quality hoặc khôi phục dữ liệu gameplay đã lọc; giới hạn corpus và các bước
review gameplay vẫn theo [audit trợ lý](../testing/2026-10-29_elden-ring-assistant-capabilities.md).
Kết quả đo ngày 29/10 chỉ là đoạn resume, được giữ nguyên để phản ánh lịch sử, không đổi thành thời gian toàn bộ.
