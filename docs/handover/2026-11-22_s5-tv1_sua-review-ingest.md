# [S5] TV1 sửa review ingest (mục 3, 16, 20)

Nguồn: `2026-11-17_s5-tv2_ra-soat-ma-toan-he-thong.md`. Nhánh `fix/s5-tv1-review-ingest`.

## Đã sửa

- **#3 (P1)** `ingest update --batch-pages/--max-pages` nhận 0/âm: bước lô <= 0 làm vòng lặp rỗng nhưng vẫn báo hoàn tất và đẩy watermark.
  CLI dùng argparse `type=positive_int`; `run_update` kiểm tra `batch_pages` (đối số hoặc `[update] batch_pages`) và `max_pages`
  ngay đầu hàm, trước khi đọc state, nguồn hay index. Sai thì `ValueError` (CLI trả mã 2).
- **#16** `__import__("itertools"/"re")` trong `ingest/chunk/full.py`, `ingest/transform/full.py` đổi sang import đầu file.
- **#20** `scripts/data_pipeline.py::tokenizer()` bỏ `TOKENIZER_GLOB` riêng, dùng `ingest.update_builder.tokenizer_path(BACKEND_ROOT / settings.rag_models_dir)`
  như `ingest update`. `--tokenizer` tường minh vẫn thắng.

## Kiểm tra

- Test mới: `test_ingest_update_limits.py` (state/index/jobs/nguồn không bị chạm), `test_pipeline_tokenizer_lookup.py` (hai thư mục cache giả).
- ruff check/format sạch; `pytest tests/unit`: 969 passed, 20 skipped.

## Chưa kiểm chứng

Chưa chạy pipeline thật với model/mạng. Đổi nơi tìm tokenizer: máy chỉ có model ở `models/fastembed` mặc định vẫn khớp (cùng giá trị mặc định).
